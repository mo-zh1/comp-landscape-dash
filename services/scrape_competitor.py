"""
Service 1 — scrape_competitor (deep research)
Input : company_name, website_url, linkedin_url (optional)
Output: structured dict with company profile + raw_pages for provenance

Research depth (per company):
  1. Official website pages (main + /about /team /pricing /careers /blog /technology)
  2. Wayback Machine CDX — domain history & alternate subdomains
  3. Funding news (TechCrunch, Crunchbase, news sites)
  4. Founder / leadership search
  5. Technology / architecture disclosure
  6. Hiring signal (job titles from careers page → growth / direction)
  7. Academic papers (arXiv / Google Scholar mentions)
  8. Partnerships / customer press releases
"""
import textwrap

import httpx

from core import config
from services.utils import fetch_page, llm, llm_with_web_search, parse_json, web_search

_SCHEMA = """
Return ONLY a JSON object:
{
  "company_name": str,
  "canonical_name": str,
  "website": str | null,
  "linkedin_url": str | null,
  "hq_city": str | null,
  "hq_country": str | null,
  "founded_year": int | null,
  "founders": [{"name": str, "role": str, "background": str | null, "source_url": str | null}],
  "target_customer": str | null,
  "core_product": str | null,
  "pricing_model": str | null,
  "stage_focus": str | null,
  "business_model_summary": str | null,
  "technical": str | null,
  "latest_round": {
    "type": str | null,
    "amount_usd": float | null,
    "date": str | null,
    "lead_investors": [str],
    "other_investors": [str],
    "valuation_usd": float | null,
    "source_url": str | null
  } | null,
  "funding_history": [{"type": str, "amount_usd": float|null, "date": str|null, "investors": [str], "source_url": str|null}],
  "investors": [{"name": str, "role": "lead"|"follow"|"strategic", "source_url": str|null}],
  "customers": [{"name": str, "type": "anchor"|"pilot"|"named", "source_url": str|null}],
  "partners": [{"name": str, "type": str, "source_url": str|null}],
  "hiring_signals": [str],
  "tech_disclosure": {
    "architecture_claims": [str],
    "data_type": str | null,
    "stage_focus": str | null,
    "model_types": [str]
  },
  "alternate_domains": [str],
  "confidence_per_field": {field_name: float},
  "sources": [{"url": str, "tier": int, "type": str}]
}
Rules:
- unknown → null
- confidence: single indirect source = 0.4, multi-source = 0.95, official = 0.8
- Only cite real URLs from the evidence. NEVER invent data.
- hiring_signals: extract 3-5 job titles from careers page to indicate growth direction
- alternate_domains: list any non-primary domains found (e.g. old name, product subdomain)
"""


def _wayback_urls(domain: str) -> list[str]:
    """Query Wayback Machine CDX for archived URLs of this domain."""
    try:
        r = httpx.get(
            "http://web.archive.org/cdx/search/cdx",
            params={
                "url": f"*.{domain}",
                "output": "json",
                "fl": "original",
                "collapse": "urlkey",
                "limit": "30",
                "filter": "statuscode:200",
            },
            timeout=10,
        )
        data = r.json()
        # first row is header ["original"]
        return [row[0] for row in data[1:] if row] if len(data) > 1 else []
    except Exception:
        return []


def _domain(url: str) -> str:
    """Extract bare domain from URL."""
    return url.replace("https://", "").replace("http://", "").split("/")[0].lstrip("www.")


def _claude_research(
    company_name: str, website_url: str | None
) -> tuple[str, list[dict]]:
    """
    Deep web research on a single company via Anthropic web_search + web_fetch.
    Returns (synthesised_report, fetched_pages) where fetched_pages is a list
    of {"url", "content"} dicts that the caller stores alongside scraped HTML.
    Model is opus-4-7; each tool capped at 5 invocations.
    """
    prompt = textwrap.dedent(f"""
        Research the company "{company_name}" (website: {website_url or 'unknown'})
        as a competitive-intelligence analyst.

        Use web_search to find relevant URLs, then web_fetch to pull full page
        contents for the most informative ones. Cover:
          • Funding rounds, investors, valuations, lead vs follow
          • Founders / leadership backgrounds (LinkedIn, prior companies)
          • Technology / architecture / model claims (papers, blog posts)
          • Customers, pilots, named partnerships
          • Hiring signals (open roles, team growth)
          • Academic publications (arXiv, peer-reviewed)

        Return a structured plain-text report. For every fact, cite the source URL
        inline like [source: https://...]. Mark unknowns explicitly. Do not invent.
    """).strip()
    try:
        return llm_with_web_search(prompt, max_uses=5, max_tokens=4096)
    except Exception as e:
        print(f"    [claude_research] ✗ failed: {e}")
        return "", []


def run(
    company_name: str,
    website_url: str | None = None,
    linkedin_url: str | None = None,
) -> dict:
    pages_md:  dict[str, str] = {}   # url → markdown (LLM context)
    raw_pages: dict[str, str] = {}   # url → raw HTML (provenance)
    sources_used: list[dict] = []

    def _add(url: str, tier: int, src_type: str):
        if url in pages_md:
            return
        md, html = fetch_page(url)
        if md:
            pages_md[url] = md
            raw_pages[url] = html
            sources_used.append({"url": url, "tier": tier, "type": src_type})

    # 1. official website pages
    if website_url:
        suffixes = ["", "/about", "/about-us", "/team", "/pricing",
                    "/careers", "/jobs", "/blog", "/technology", "/solution", "/platform"]
        for suffix in suffixes[:config.MAX_PAGES_PER_COMPANY]:
            _add(website_url.rstrip("/") + suffix, 1, "website")

    # 2. Wayback Machine — find alternate subdomains / old domains
    alternate_domains: list[str] = []
    if website_url:
        domain = _domain(website_url)
        wayback_urls = _wayback_urls(domain)
        # extract unique subdomains from wayback results
        seen_sub: set[str] = set()
        for u in wayback_urls:
            sub_domain = _domain(u)
            if sub_domain != domain and sub_domain not in seen_sub:
                seen_sub.add(sub_domain)
                alternate_domains.append(sub_domain)
        # fetch any interesting alternate pages (app., docs., product.)
        for sub in alternate_domains[:3]:
            if any(prefix in sub for prefix in ["app.", "docs.", "product.", "platform."]):
                _add(f"https://{sub}", 1, "website_subdomain")

    # 3. web research — Serper if configured, else fall back to Claude web_search
    if config.SERPER_API_KEY:
        search_batches = [
            (f'"{company_name}" funding round raises', 2, "news"),
            (f'"{company_name}" site:techcrunch.com OR site:betakit.com', 2, "news"),
            (f'"{company_name}" series seed "million" investors', 2, "news"),
            (f'"{company_name}" founder CEO co-founder background', 2, "leadership"),
            (f'"{company_name}" founded by team LinkedIn', 2, "leadership"),
            (f'"{company_name}" technology architecture machine learning AI model', 2, "tech"),
            (f'"{company_name}" research paper arXiv publication', 3, "academic"),
            (f'"{company_name}" partnership customer pilot mining company', 2, "partnership"),
            (f'"{company_name}" mining exploration AI subsurface', 2, "general"),
        ]
        for query, tier, src_type in search_batches:
            for hit in web_search(query, n=3):
                url = hit["url"]
                if url not in pages_md:
                    _add(url, tier, src_type)
    else:
        report, fetched = _claude_research(company_name, website_url)
        if report:
            key = "anthropic://web_search"
            pages_md[key]  = report
            raw_pages[key] = report
            sources_used.append({"url": key, "tier": 2, "type": "claude_research"})
        for p in fetched:
            url = p["url"]
            if url not in pages_md:
                pages_md[url]  = p["content"]
                raw_pages[url] = p["content"]
                sources_used.append({"url": url, "tier": 2, "type": "claude_fetched"})

    # cap total pages
    pages_md = dict(list(pages_md.items())[:max(config.MAX_PAGES_PER_COMPANY, 15)])

    context = "\n".join(
        f"--- SOURCE [{src['type'].upper()}]: {url} ---\n{text[:3000]}\n"
        for (url, text), src in zip(pages_md.items(), sources_used)
    ) or f"No pages fetched for {company_name}."

    wayback_note = (
        f"\nWayback Machine found these alternate domains: {', '.join(alternate_domains[:10])}"
        if alternate_domains else ""
    )

    prompt = textwrap.dedent(f"""
        You are a competitive intelligence analyst doing deep research.

        Company: {company_name}
        Website: {website_url or 'unknown'}
        {wayback_note}

        Evidence ({len(pages_md)} pages fetched):
        {context}

        {_SCHEMA}
    """).strip()

    try:
        raw = llm(prompt, max_tokens=8096)
        result = parse_json(raw)
    except Exception as e:
        result = {
            "company_name": company_name,
            "canonical_name": company_name,
            "website": website_url,
            "confidence_per_field": {},
            "sources": sources_used,
            "_error": str(e),
        }

    result.setdefault("sources", sources_used)
    result.setdefault("alternate_domains", alternate_domains)
    result["raw_pages"] = raw_pages
    return result
