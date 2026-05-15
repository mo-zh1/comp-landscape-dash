"""
Export DB → data.json for static HTML dashboard.
Run after any pipeline stage: python export.py
Also called by GitHub Actions workflows before committing.
"""
import json
import os
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from core.db import Database
from core import config


def _clean(v):
    """Make values JSON-serialisable."""
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if v is None or v == "":
        return None
    return v


def _clean_dict(d: dict) -> dict:
    return {k: _clean(v) for k, v in d.items()}


def run(out_path: str = "data.json"):
    db = Database(config.DB_PATH)

    companies  = [_clean_dict(c) for c in db.get_companies()]
    events     = [_clean_dict(e) for e in db.get_events(limit=300)]
    investors  = [_clean_dict(r) for r in db.get_all_investors()]
    candidates = [_clean_dict(c) for c in db.get_candidates(status="pending")]
    digests    = [_clean_dict(d) for d in db.get_digests(limit=10)]

    # parse event payloads from JSON strings
    for e in events:
        if isinstance(e.get("payload"), str):
            try:
                e["payload"] = json.loads(e["payload"])
            except Exception:
                e["payload"] = {}

    # parse candidate initial_evidence
    for c in candidates:
        if isinstance(c.get("initial_evidence"), str):
            try:
                c["initial_evidence"] = json.loads(c["initial_evidence"])
            except Exception:
                c["initial_evidence"] = {}

    stats = {
        "total":    len(companies),
        "active":   sum(1 for c in companies if c.get("status") == "active"),
        "stealth":  sum(1 for c in companies if c.get("status") == "stealth"),
        "acquired": sum(1 for c in companies if c.get("status") == "acquired"),
        "conflicts_pending":  db.count_conflicts("pending"),
        "candidates_pending": db.count_candidates("pending"),
    }

    data = {
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "stats": stats,
        "companies":  companies,
        "events":     events,
        "investors":  investors,
        "candidates": candidates,
        "digests":    digests,
    }

    Path(out_path).write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"Exported → {out_path}  ({len(companies)} companies · {len(events)} events · {len(digests)} digests)")
    db.close()


if __name__ == "__main__":
    run()
