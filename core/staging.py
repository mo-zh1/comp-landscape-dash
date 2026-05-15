"""
Staging layer — buffers pipeline output in staging.db for human review
before any data reaches the final competitors.db.

Design: pipeline writes here; review_server.py reads and approves into final DB.
"""
import json
import sqlite3
from datetime import date, datetime
from uuid import uuid4

from .db import Database
from .resolver import event_fingerprint, classify_source

STAGING_DB_PATH = "staging.db"

_SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id          TEXT PRIMARY KEY,
    trigger     TEXT NOT NULL,
    started_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    status      TEXT DEFAULT 'running',
    summary     TEXT
);

CREATE TABLE IF NOT EXISTS staged_updates (
    id           TEXT PRIMARY KEY,
    run_id       TEXT REFERENCES pipeline_runs(id),
    company_id   TEXT,
    company_name TEXT,
    field_name   TEXT NOT NULL,
    old_value    TEXT,
    new_value    TEXT NOT NULL,
    source_url   TEXT,
    source_tier  INTEGER,
    confidence   REAL,
    status       TEXT DEFAULT 'pending',
    reviewed_at  TIMESTAMP,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staged_events (
    id           TEXT PRIMARY KEY,
    run_id       TEXT REFERENCES pipeline_runs(id),
    company_id   TEXT,
    company_name TEXT,
    event_type   TEXT NOT NULL,
    event_date   DATE,
    payload      TEXT,
    fingerprint  TEXT,
    source_url   TEXT,
    source_tier  INTEGER,
    confidence   REAL,
    is_duplicate INTEGER DEFAULT 0,
    status       TEXT DEFAULT 'pending',
    reviewed_at  TIMESTAMP,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staged_candidates (
    id               TEXT PRIMARY KEY,
    run_id           TEXT REFERENCES pipeline_runs(id),
    discovered_name  TEXT NOT NULL,
    discovered_url   TEXT,
    discovery_source TEXT,
    discovery_reason TEXT,
    initial_evidence TEXT,
    status           TEXT DEFAULT 'pending',
    reviewed_at      TIMESTAMP,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_su_status ON staged_updates(status);
CREATE INDEX IF NOT EXISTS idx_su_run    ON staged_updates(run_id);
CREATE INDEX IF NOT EXISTS idx_se_status ON staged_events(status);
CREATE INDEX IF NOT EXISTS idx_se_run    ON staged_events(run_id);
CREATE INDEX IF NOT EXISTS idx_sc_status ON staged_candidates(status);
CREATE INDEX IF NOT EXISTS idx_sc_run    ON staged_candidates(run_id);
"""

# fields staged from scrape_competitor results (field_name → default source tier)
_STAGE_FIELDS: dict[str, int] = {
    "website": 1,
    "founded_year": 1,
    "hq_city": 2,
    "hq_country": 2,
    "target_customer": 2,
    "core_product": 2,
    "pricing_model": 2,
    "business_model_summary": 2,
}


class StagingDB:
    def __init__(self, path: str = STAGING_DB_PATH):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def close(self):
        self.conn.close()

    def _one(self, sql, params=()):
        row = self.conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def _q(self, sql, params=()):
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    # ── run lifecycle ──────────────────────────────────────────────────────────

    def start_run(self, trigger: str) -> str:
        rid = uuid4().hex[:12]
        self.conn.execute(
            "INSERT INTO pipeline_runs (id, trigger) VALUES (?,?)", (rid, trigger)
        )
        self.conn.commit()
        return rid

    def finish_run(self, run_id: str, status: str = "done", summary: dict | None = None):
        self.conn.execute(
            "UPDATE pipeline_runs SET status=?, finished_at=?, summary=? WHERE id=?",
            (status, datetime.utcnow().isoformat(), json.dumps(summary or {}), run_id),
        )
        self.conn.commit()

    # ── inserts ───────────────────────────────────────────────────────────────

    def insert_update(self, run_id, company_id, company_name,
                      field, old, new, source_url, tier, conf):
        self.conn.execute(
            """INSERT INTO staged_updates
               (id, run_id, company_id, company_name, field_name,
                old_value, new_value, source_url, source_tier, confidence)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (uuid4().hex[:12], run_id, company_id, company_name, field,
             str(old) if old is not None else None, str(new),
             source_url, tier, conf),
        )
        self.conn.commit()

    def insert_event(self, run_id, company_id, company_name,
                     event_type, event_date, payload, fp,
                     source_url, tier, conf, is_dup=False):
        self.conn.execute(
            """INSERT INTO staged_events
               (id, run_id, company_id, company_name, event_type, event_date,
                payload, fingerprint, source_url, source_tier, confidence, is_duplicate)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (uuid4().hex[:12], run_id, company_id, company_name,
             event_type, event_date,
             json.dumps(payload) if isinstance(payload, dict) else payload,
             fp, source_url, tier, conf, int(is_dup)),
        )
        self.conn.commit()

    def insert_candidate(self, run_id, name, url, source, reason, evidence):
        self.conn.execute(
            """INSERT INTO staged_candidates
               (id, run_id, discovered_name, discovered_url,
                discovery_source, discovery_reason, initial_evidence)
               VALUES (?,?,?,?,?,?,?)""",
            (uuid4().hex[:12], run_id, name, url, source, reason,
             json.dumps(evidence) if isinstance(evidence, dict) else evidence),
        )
        self.conn.commit()

    # ── reads ─────────────────────────────────────────────────────────────────

    def get_pending(self) -> dict:
        return {
            "updates":    self._q("SELECT * FROM staged_updates    WHERE status='pending' ORDER BY created_at DESC"),
            "events":     self._q("SELECT * FROM staged_events     WHERE status='pending' ORDER BY created_at DESC"),
            "candidates": self._q("SELECT * FROM staged_candidates WHERE status='pending' ORDER BY created_at DESC"),
        }

    def get_runs(self, limit: int = 50) -> list[dict]:
        runs = self._q(
            "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT ?", (limit,)
        )
        for r in runs:
            r["counts"] = {
                "updates":    self._one("SELECT COUNT(*) n FROM staged_updates    WHERE run_id=?", (r["id"],))["n"],
                "events":     self._one("SELECT COUNT(*) n FROM staged_events     WHERE run_id=?", (r["id"],))["n"],
                "candidates": self._one("SELECT COUNT(*) n FROM staged_candidates WHERE run_id=?", (r["id"],))["n"],
            }
        return runs

    def get_run_items(self, run_id: str) -> dict:
        """Return all items staged in a specific run (any status)."""
        return {
            "updates":    self._q("SELECT * FROM staged_updates    WHERE run_id=? ORDER BY created_at", (run_id,)),
            "events":     self._q("SELECT * FROM staged_events     WHERE run_id=? ORDER BY created_at", (run_id,)),
            "candidates": self._q("SELECT * FROM staged_candidates WHERE run_id=? ORDER BY created_at", (run_id,)),
        }

    def set_status(self, table: str, row_id: str, status: str):
        self.conn.execute(
            f"UPDATE {table} SET status=?, reviewed_at=? WHERE id=?",
            (status, datetime.utcnow().isoformat(), row_id),
        )
        self.conn.commit()

    def get_update(self, rid):    return self._one("SELECT * FROM staged_updates    WHERE id=?", (rid,))
    def get_event(self, rid):     return self._one("SELECT * FROM staged_events     WHERE id=?", (rid,))
    def get_candidate(self, rid): return self._one("SELECT * FROM staged_candidates WHERE id=?", (rid,))


# ── helpers called by pipeline ─────────────────────────────────────────────────

def stage_company_result(staging_db: StagingDB, final_db: Database, run_id: str,
                          company_id: str | None, company_name: str, scraped: dict):
    """Diff scraped result vs final DB; write changed fields + new events to staging."""
    company    = final_db.get_company(company_id) if company_id else {}
    source_url = (scraped.get("sources") or [{}])[0].get("url", "")

    # company field diffs
    for field, tier in _STAGE_FIELDS.items():
        new_val = scraped.get(field)
        if new_val is None:
            continue
        old_val = (company or {}).get(field)
        if str(old_val or "") == str(new_val):
            continue
        conf = scraped.get("confidence_per_field", {}).get(field, 0.5)
        staging_db.insert_update(
            run_id, company_id, company_name, field,
            old_val, new_val, source_url, tier, conf,
        )

    # latest round field diffs + funding_round event
    lr = scraped.get("latest_round")
    if lr and lr.get("type"):
        for fld, sfld in [
            ("latest_round_type", "type"),
            ("latest_round_amount_usd", "amount_usd"),
            ("latest_round_date", "date"),
        ]:
            v = lr.get(sfld)
            if v is None:
                continue
            old_val = (company or {}).get(fld)
            if str(old_val or "") == str(v):
                continue
            staging_db.insert_update(
                run_id, company_id, company_name, fld,
                old_val, v, source_url, 2, 0.8,
            )

        try:
            ev_date = date.fromisoformat(lr["date"][:10])
        except Exception:
            ev_date = date.today()
        fp     = event_fingerprint(company_id or "probe", "funding_round", ev_date, lr)
        is_dup = bool(final_db.get_event_by_fingerprint(fp)) if company_id else False
        staging_db.insert_event(
            run_id, company_id, company_name, "funding_round",
            ev_date.isoformat(), lr, fp, source_url, 2, 0.8, is_dup,
        )


def stage_rss_event(staging_db: StagingDB, final_db: Database, run_id: str,
                    company_id: str, company_name: str, event: dict):
    """Stage a single RSS-extracted event for review."""
    ev_date_str = event.get("event_date") or date.today().isoformat()
    try:
        ev_date = date.fromisoformat(ev_date_str[:10])
    except Exception:
        ev_date = date.today()

    event_type = event.get("event_type", "unknown")
    payload    = event.get("payload", {})
    source_url = event.get("source_url", "")
    tier       = classify_source(source_url)[1] if source_url else 3
    fp         = event_fingerprint(company_id, event_type, ev_date, payload)
    is_dup     = bool(final_db.get_event_by_fingerprint(fp))

    staging_db.insert_event(
        run_id, company_id, company_name, event_type,
        ev_date.isoformat(), payload, fp, source_url, tier,
        event.get("confidence", 0.5), is_dup,
    )
