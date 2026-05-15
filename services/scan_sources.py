"""
Service — scan_sources
Weekly scan of curated sources to discover new mining/subsurface AI companies.

Sources:
  1. Cathay Innovation Medium (RSS)          ✅ working
  2. Mining.com (Serper keyword search)       ⚠️  requires SERPER_API_KEY
  3. BHP Ventures (Serper search fallback)    ⚠️  requires SERPER_API_KEY (direct page is bot-protected)
  4. Rio Tinto Ventures (Serper search)       ⚠️  requires SERPER_API_KEY (old direct URL is 404)
  5. Techstars mining cohorts (Serper)        ⚠️  requires SERPER_API_KEY
  6. arXiv physics.geo-ph + cs.LG (API)      ✅ working
  7. LinkedIn mining AI startups (Serper)     ⚠️  requires SERPER_API_KEY
  8. Claude direct discovery (web_search)    ✅ always works (paid per search)

All output is source-backed: every field comes directly from the source text.
No LLM fabrication. Unknown → null / omit.

Output: {"candidates": [{"name", "website", "summary", "signals", "source_url"}]}
"""
import textwrap
from xml.etree import ElementTree as ET

import httpx

from services.utils import fetch_page, llm, llm_with_web_search, parse_json, web_search

# ── extraction prompt (reused per source) ──────────────────────────────────

_EXTRACT_PROMPT = textwrap.dedent("""
    You are extracting competitor companies from the source below.

    Source URL: {source_url}
    ---
    {content}
    ---

    Extract ONLY companies explicitly mentioned that:
    - Use AI / machine learning for mineral exploration, mining, or subsurface analysis
    - Are startups or newer products (NOT established giants like Schlumberger, Halliburton,
      Hexagon, Trimble, Esri, Baker Hughes, or large universities/national labs)

    For each company:
    - name: company name exactly as written in the source
    - website: ONLY if a full URL is explicitly stated — otherwise null
    - summary: one-sentence verbatim quote or close paraphrase (≤25 words) from the source
    - signals: funding amount / stage / investors ONLY if explicitly stated with specifics — otherwise null
    - source_url: {source_url}

    Return ONLY JSON:
    {{"companies": [
      {{"name": str, "website": str|null, "summary": str, "signals": str|null, "source_url": str}}
    ]}}

    Rules:
    - If no qualifying companies found → {{"companies": []}}
    - Do not infer, estimate, or generate any information not in the text
    - Skip companies already well-known as non-AI / non-mining
""")


def _extract(content: str, source_url: str) -> list[dict]:
    if not content or not content.strip():
        print(f"    [scan] ⚠ empty content for {source_url} — skipping LLM call")
        return []
    prompt = _EXTRACT_PROMPT.format(
        source_url=source_url,
        content=content[:6000],
    )
    try:
        raw = llm(prompt, max_tokens=1024)
        return parse_json(raw).get("companies", [])
    except Exception as e:
        print(f"    [scan] ⚠ LLM/parse error for {source_url}: {e}")
        return []


# ── source fetchers ────────────────────────────────────────────────────────

def _fetch_rss(url: str, max_items: int = 15) -> str:
    """Fetch RSS feed and return concatenated text of recent items."""
    try:
        r = httpx.get(url, timeout=15, headers={"User-Agent": "CompIntel/1.0"}, follow_redirects=True)
        r.raise_for_status()
        root = ET.fromstring(r.text)
    except Exception as e:
        print(f"    [rss] ✗ failed {url}: {e}")
        return ""

    items = []
    for item in list(root.iter("item"))[:max_items]:
        title = (item.findtext("title") or "").strip()
        link  = (item.findtext("link")  or "").strip()
        desc  = (item.findtext("description") or "").strip()
        items.append(f"TITLE: {title}\nURL: {link}\n{desc[:500]}")
    return "\n---\n".join(items)


def _fetch_arxiv() -> str:
    """Fetch recent arXiv papers in physics.geo-ph and cs.LG categories."""
    url = (
        "https://export.arxiv.org/api/query"  # https — arXiv dropped plain http
        "?search_query=cat:physics.geo-ph+AND+cat:cs.LG"
        "&sortBy=submittedDate&sortOrder=descending&max_results=12"
    )
    try:
        r = httpx.get(url, timeout=20, headers={"User-Agent": "CompIntel/1.0"}, follow_redirects=True)
        r.raise_for_status()
        root = ET.fromstring(r.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = []
        for entry in root.findall("atom:entry", ns)[:12]:
            title   = (entry.findtext("atom:title",   "", ns) or "").strip()
            summary = (entry.findtext("atom:summary", "", ns) or "").strip()
            link    = next(
                (e.get("href", "") for e in entry.findall("atom:link", ns) if e.get("rel") == "alternate"),
                ""
            )
            authors = []
            for auth in entry.findall("atom:author", ns):
                name = auth.findtext("atom:name", "", ns) or ""
                aff  = auth.findtext("atom:affiliation", "", ns) or ""
                if aff:
                    authors.append(f"{name} ({aff})")
                else:
                    authors.append(name)
            entries.append(
                f"TITLE: {title}\nURL: {link}\n"
                f"AUTHORS: {', '.join(authors[:5])}\n"
                f"ABSTRACT: {summary[:400]}"
            )
        return "\n---\n".join(entries)
    except Exception as e:
        print(f"    [arxiv] ✗ failed: {e}")
        return ""


def _claude_discover(known: set[str]) -> list[dict]:
    """
    Use Claude's native web_search to discover new mining/subsurface AI companies.
    Returns candidates already in the standard schema (no _extract needed).
    """
    skip_clause = f"Already known (skip): {', '.join(sorted(known)[:30])}\n" if known else ""
    prompt = textwrap.dedent(f"""
        Search the web to discover startup companies using AI/ML for mineral exploration,
        mining operations, or subsurface/geophysics analysis. Focus on 2024-2026 activity:
        recent funding, product launches, accelerator cohorts, corporate venture portfolios
        (BHP Ventures, Rio Tinto Ventures, Cathay Innovation, Techstars Mining), news.

        {skip_clause}
        Skip incumbents: Schlumberger, Halliburton, Hexagon, Trimble, Esri, Baker Hughes,
        large universities, national labs.

        Return ONLY JSON, no prose:
        {{"companies": [
          {{"name": str,
            "website": str|null,
            "summary": str (≤25 words, verbatim or close paraphrase from a cited page),
            "signals": str|null (funding amount / stage / investors, only if explicitly stated),
            "source_url": str (URL where you found this company)}}
        ]}}

        Rules: only cite real URLs you actually searched. Never invent. Unknown → null.
    """).strip()
    try:
        raw, _pages = llm_with_web_search(prompt, max_uses=5, max_tokens=4096)
        return parse_json(raw).get("companies", [])
    except Exception as e:
        print(f"    [claude_discover] ✗ failed: {e}")
        return []


def _search_text(queries: list[str], n_per_query: int = 5) -> str:
    """
    Run Serper searches and return concatenated snippets.
    Returns empty string (with warning) if SERPER_API_KEY is not configured.
    """
    results = []
    seen: set[str] = set()
    for q in queries:
        hits = web_search(q, n=n_per_query)
        if not hits:
            # web_search returns [] both for no results AND for missing key —
            # the warning is emitted once by utils.web_search when key is absent
            continue
        for hit in hits:
            url = hit.get("url", "")
            if url not in seen:
                seen.add(url)
                results.append(f"URL: {url}\nTITLE: {hit.get('title','')}\n{hit.get('snippet','')}")
    return "\n---\n".join(results)


# ── main entry point ───────────────────────────────────────────────────────

def run(known_companies: list[str] | None = None) -> dict:
    """
    Scan all curated sources. Returns candidates with source-backed info.
    known_companies: optional list of canonical names to skip.
    """
    known = set(known_companies or [])
    all_candidates: list[dict] = []

    sources = [
        # (label, source_url, content_fn)

        # 1. Cathay Innovation Medium RSS — direct feed, no key required
        ("Cathay Innovation Medium",
         "https://medium.com/cathay-innovation",
         lambda: _fetch_rss("https://medium.com/feed/cathay-innovation")),

        # 2. Mining.com — Serper keyword search (requires SERPER_API_KEY)
        ("Mining.com AI",
         "https://www.mining.com",
         lambda: _search_text([
             'site:mining.com "artificial intelligence" OR "machine learning" mining startup',
             'site:mining.com "AI" exploration technology company raises',
         ])),

        # 3. BHP Ventures — direct page is bot-protected; use Serper instead
        ("BHP Ventures",
         "https://www.bhp.com/what-we-do/bhp-ventures",
         lambda: _search_text([
             'BHP Ventures portfolio startup mining AI technology investment',
             'site:bhp.com ventures portfolio company',
         ])),

        # 4. Rio Tinto Ventures — old direct URL is 404; use Serper instead
        ("Rio Tinto Ventures",
         "https://www.riotinto.com",
         lambda: _search_text([
             'Rio Tinto Ventures portfolio startup mining AI technology investment',
             'site:riotinto.com ventures portfolio company startup',
         ])),

        # 5. Techstars Mining — Serper search (requires SERPER_API_KEY)
        ("Techstars Mining",
         "https://www.techstars.com",
         lambda: _search_text([
             'techstars mining OR exploration AI portfolio company startup',
             'techstars "mineral" OR "geophysics" cohort company',
         ])),

        # 6. arXiv geo-ph + cs.LG — uses https (http redirects break raise_for_status)
        ("arXiv geo-ph + cs.LG",
         "https://arxiv.org",
         _fetch_arxiv),

        # 7. LinkedIn — Serper search for company pages (requires SERPER_API_KEY)
        ("LinkedIn Mining AI",
         "https://www.linkedin.com",
         lambda: _search_text([
             'site:linkedin.com/company mining AI exploration startup "seed" OR "Series A"',
             'site:linkedin.com/company subsurface AI mineral exploration startup founded',
             'site:linkedin.com/company geophysics machine learning startup mining',
         ])),
    ]

    for label, source_url, content_fn in sources:
        print(f"  [scan] {label}")
        try:
            content = content_fn()
            companies = _extract(content, source_url)
            new = [c for c in companies if c.get("name") and c["name"] not in known]
            if new:
                print(f"    → {len(new)} candidate(s) found")
            all_candidates.extend(new)
        except Exception as e:
            print(f"    [scan] ✗ error: {e}")

    # 8. Claude direct discovery — independent broad search via Anthropic web_search
    print("  [scan] Claude direct discovery (web_search)")
    try:
        claude_finds = _claude_discover(known)
        new = [c for c in claude_finds if c.get("name") and c["name"] not in known]
        if new:
            print(f"    → {len(new)} candidate(s) found")
        all_candidates.extend(new)
    except Exception as e:
        print(f"    [scan] ✗ error: {e}")

    # deduplicate by name (case-insensitive)
    seen_names: set[str] = set()
    deduped: list[dict] = []
    for c in all_candidates:
        key = c["name"].lower().strip()
        if key not in seen_names:
            seen_names.add(key)
            deduped.append(c)

    print(f"  [scan] total: {len(deduped)} unique candidates")
    return {"candidates": deduped}
