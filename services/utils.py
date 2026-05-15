"""
Shared utilities for all services.
Centralises: Anthropic client, web search (Serper), page fetch (httpx + BS4).
"""
import json
from functools import lru_cache

import anthropic
import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify

from core import config

# ── LLM client ────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_client() -> anthropic.Anthropic:
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set — copy .env.example → .env")
    return anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


def llm(prompt: str, max_tokens: int = 4096) -> str:
    """Single-turn LLM call. Returns raw text."""
    response = get_client().messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def llm_with_web_search(
    prompt: str, max_uses: int = 5, max_tokens: int = 4096
) -> tuple[str, list[dict]]:
    """
    LLM call with Anthropic's native web_search + web_fetch server-tools.
    Claude can search, fetch full page bodies, and synthesise — all server-side.

    Returns: (synthesised_text, fetched_pages)
        fetched_pages = [{"url": str, "content": str}, ...] for every page
        Claude actually pulled (so callers can store raw evidence downstream).

    Model is pinned to opus-4-7; each tool capped at `max_uses` invocations.
    """
    response = get_client().messages.create(
        model="claude-opus-4-7",
        max_tokens=max_tokens,
        tools=[
            {"type": "web_search_20260209", "name": "web_search", "max_uses": max_uses},
            {"type": "web_fetch_20260209",  "name": "web_fetch",  "max_uses": max_uses,
             "citations": {"enabled": True}},
        ],
        messages=[{"role": "user", "content": prompt}],
    )
    text_parts: list[str] = []
    fetched:    list[dict] = []
    for b in response.content:
        t = getattr(b, "type", "")
        if t == "text":
            text_parts.append(b.text)
        elif t == "web_fetch_tool_result":
            page = _page_from_fetch(b.content)
            if page:
                fetched.append(page)
    return "\n".join(text_parts).strip(), fetched


def _page_from_fetch(c) -> dict | None:
    """Pull (url, body) from a web_fetch_tool_result.content payload (best-effort)."""
    url  = getattr(c, "url", None)
    body = getattr(c, "content", None)
    # body is typically a Document object — unwrap to its raw text
    if body is not None and not isinstance(body, str):
        src  = getattr(body, "source", None)
        body = (
            getattr(body, "text", None)
            or getattr(src, "data", None)
            or getattr(src, "text", None)
            or str(body)
        )
    return {"url": url, "content": str(body)[:20000]} if url and body else None


def parse_json(raw: str) -> dict | list:
    """Extract and parse JSON from LLM output (handles ```json fences)."""
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0]
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0]
    return json.loads(raw.strip())


# ── Web helpers ───────────────────────────────────────────────────────────────

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CompIntel/1.0)"}
_serper_warned = False


def fetch_page(url: str, timeout: int = 15) -> tuple[str, str]:
    """
    Fetch URL → (markdown_text, raw_html).
    Returns ('', '') on failure.
    """
    try:
        r = httpx.get(url, timeout=timeout, follow_redirects=True, headers=_HEADERS)
        r.raise_for_status()
        raw_html = r.text
        soup = BeautifulSoup(raw_html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        md = markdownify(str(soup), heading_style="ATX")
        return md[:8000], raw_html[:20000]
    except Exception:
        return "", ""


def web_search(query: str, n: int = 8) -> list[dict]:
    """
    Search via Serper API → list of {title, url, snippet}.
    Returns [] if SERPER_API_KEY is not set (prints a one-time warning).
    """
    global _serper_warned
    if not config.SERPER_API_KEY:
        if not _serper_warned:
            print("    [serper] ⚠ SERPER_API_KEY not set — web search disabled (see .env.example)")
            _serper_warned = True
        return []
    try:
        r = httpx.post(
            "https://google.serper.dev/search",
            json={"q": query, "num": n},
            headers={"X-API-KEY": config.SERPER_API_KEY},
            timeout=15,
        )
        r.raise_for_status()
        return [
            {"title": x.get("title", ""), "url": x.get("link", ""), "snippet": x.get("snippet", "")}
            for x in r.json().get("organic", [])
        ]
    except Exception:
        return []
