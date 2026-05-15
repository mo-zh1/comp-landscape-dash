"""Service runners — each exposes a run() function."""
from .scrape_competitor import run as scrape_competitor
from .generate_digest   import run as generate_digest
from .scan_sources      import run as scan_sources

__all__ = [
    "scrape_competitor",
    "generate_digest",
    "scan_sources",
]
