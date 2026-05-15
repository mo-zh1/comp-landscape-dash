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
