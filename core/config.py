"""
Central configuration — override any value via .env or environment variables.
Copy .env.example → .env and fill in your API keys.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ──────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
SERPER_API_KEY: str = os.environ.get("SERPER_API_KEY", "")  # optional — web search

# ── LLM ───────────────────────────────────────────────────────────────────────

ANTHROPIC_MODEL: str = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-7")

# ── Storage ───────────────────────────────────────────────────────────────────

DB_PATH: str = os.environ.get("DB_PATH", "competitors.db")
RAW_SIGNAL_RETENTION_DAYS: int = 1095  # keep raw scraped content for 3 years

# ── Pipeline — RSS feeds to monitor (daily run) ───────────────────────────────

RSS_FEEDS: list[str] = [
    "https://techcrunch.com/category/startups/feed/",
    "https://betakit.com/feed/",
    "https://www.mining.com/feed/",
    # add more feeds here, e.g. "https://www.australianmining.com.au/feed/"
]

# ── Pipeline — keywords for new competitor discovery (monthly run) ─────────────

INDUSTRY_KEYWORDS: list[str] = [
    "mineral exploration AI",
    "mining AI subsurface",
    "geophysics machine learning startup",
]

# ── Entity resolution thresholds ──────────────────────────────────────────────
# confidence >= AUTO_MERGE_HIGH   → merge silently
# confidence >= AUTO_MERGE_LOW    → merge + flag for review
# confidence >= CONFLICT_FLOOR    → push to conflicts queue
# confidence <  CONFLICT_FLOOR    → treat as new candidate

AUTO_MERGE_HIGH: float = 0.95
AUTO_MERGE_LOW: float = 0.85
CONFLICT_FLOOR: float = 0.70

# ── Scraping ──────────────────────────────────────────────────────────────────

SCRAPE_PAGE_SUFFIXES: list[str] = ["", "/about", "/team", "/pricing", "/careers"]
MAX_PAGES_PER_COMPANY: int = 6  # cap to control token cost per scrape run

# ── Future config hooks (not yet implemented) ─────────────────────────────────
# SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")  # digest notification
# EMAIL_SMTP_HOST   = os.environ.get("EMAIL_SMTP_HOST", "")
# SUPABASE_URL      = os.environ.get("SUPABASE_URL", "")       # swap SQLite → Postgres
# SUPABASE_KEY      = os.environ.get("SUPABASE_KEY", "")
