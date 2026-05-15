"""SQLite helper — thin wrapper around sqlite3."""
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
import os

load_dotenv()

_DEFAULT_PATH = os.getenv("DB_PATH", "competitors.db")
_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class Database:
    def __init__(self, path: str = _DEFAULT_PATH):
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")

    def init_schema(self):
        self.conn.executescript(_SCHEMA_PATH.read_text())
        # migrate existing DBs: add new columns if they don't exist
        new_cols = [
            ("technical", "TEXT"),
            ("stage_description", "TEXT"),
            ("latest_round_text", "TEXT"),
            ("funding_trajectory", "TEXT"),
            ("investors_text", "TEXT"),
            ("valuation", "TEXT"),
        ]
        for col, typ in new_cols:
            try:
                self.conn.execute(f"ALTER TABLE companies ADD COLUMN {col} {typ}")
            except Exception:
                pass  # column already exists
        self.conn.commit()

    def close(self):
        self.conn.close()

    # ── internal helpers ──────────────────────────────────────────────────────

    def _q(self, sql: str, params=()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchall()

    def _one(self, sql: str, params=()) -> sqlite3.Row | None:
        return self.conn.execute(sql, params).fetchone()

    def _run(self, sql: str, params=()):
        self.conn.execute(sql, params)
        self.conn.commit()

    # ── companies ─────────────────────────────────────────────────────────────

    def get_companies(self, status: str | None = None) -> list[dict]:
        if status:
            rows = self._q(
                "SELECT * FROM companies WHERE status = ? ORDER BY canonical_name",
                (status,),
            )
        else:
            rows = self._q("SELECT * FROM companies ORDER BY canonical_name")
        return [dict(r) for r in rows]

    def get_company(self, company_id: str) -> dict | None:
        row = self._one("SELECT * FROM companies WHERE id = ?", (company_id,))
        return dict(row) if row else None

    def get_company_by_website(self, domain: str) -> dict | None:
        row = self._one(
            "SELECT * FROM companies WHERE website LIKE ?", (f"%{domain}%",)
        )
        return dict(row) if row else None

    def insert_company(self, data: dict) -> str:
        cid = data.get("id") or str(uuid4())
        self._run(
            """INSERT INTO companies
               (id, canonical_name, website, linkedin_url, hq_city, hq_country,
                founded_year, target_customer, core_product, pricing_model, stage_focus,
                latest_round_type, latest_round_amount_usd, latest_round_date,
                business_model_summary, technical, stage_description,
                latest_round_text, funding_trajectory, investors_text, valuation,
                status, confidence_score, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                cid,
                data.get("canonical_name", ""),
                data.get("website"),
                data.get("linkedin_url"),
                data.get("hq_city"),
                data.get("hq_country"),
                data.get("founded_year"),
                data.get("target_customer"),
                data.get("core_product"),
                data.get("pricing_model"),
                data.get("stage_focus"),
                data.get("latest_round_type"),
                data.get("latest_round_amount_usd"),
                data.get("latest_round_date"),
                data.get("business_model_summary"),
                data.get("technical"),
                data.get("stage_description"),
                data.get("latest_round_text"),
                data.get("funding_trajectory"),
                data.get("investors_text"),
                data.get("valuation"),
                data.get("status", "active"),
                data.get("confidence_score", 1.0),
                data.get("notes"),
            ),
        )
        return cid

    def update_company(self, company_id: str, data: dict):
        data["last_updated"] = datetime.utcnow().isoformat()
        sets = ", ".join(f"{k} = ?" for k in data)
        vals = list(data.values()) + [company_id]
        self._run(f"UPDATE companies SET {sets} WHERE id = ?", vals)

    # ── events ────────────────────────────────────────────────────────────────

    def insert_event(self, data: dict) -> str:
        eid = data.get("id") or str(uuid4())
        self._run(
            """INSERT INTO events
               (id, company_id, event_type, event_date, payload, fingerprint,
                source_url, source_tier, cross_references, extracted_by,
                confidence, raw_text)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                eid,
                data["company_id"],
                data["event_type"],
                data["event_date"],
                json.dumps(data.get("payload", {})),
                data["fingerprint"],
                data.get("source_url"),
                data.get("source_tier", 3),
                json.dumps(data.get("cross_references", [])),
                data.get("extracted_by"),
                data.get("confidence", 0.5),
                data.get("raw_text"),
            ),
        )
        return eid

    def get_event_by_fingerprint(self, fp: str) -> dict | None:
        row = self._one("SELECT * FROM events WHERE fingerprint = ?", (fp,))
        return dict(row) if row else None

    def update_event(self, event_id: str, data: dict):
        sets = ", ".join(f"{k} = ?" for k in data)
        vals = list(data.values()) + [event_id]
        self._run(f"UPDATE events SET {sets} WHERE id = ?", vals)

    def get_events_since(self, days: int = 7) -> list[dict]:
        cutoff = (datetime.utcnow() - timedelta(days=days)).date().isoformat()
        rows = self._q(
            """SELECT e.*, c.canonical_name
               FROM events e JOIN companies c ON e.company_id = c.id
               WHERE e.event_date >= ? ORDER BY e.event_date DESC""",
            (cutoff,),
        )
        return [dict(r) for r in rows]

    def get_events(self, company_id: str | None = None, limit: int = 100) -> list[dict]:
        if company_id:
            rows = self._q(
                """SELECT e.*, c.canonical_name FROM events e
                   JOIN companies c ON e.company_id = c.id
                   WHERE e.company_id = ? ORDER BY e.event_date DESC LIMIT ?""",
                (company_id, limit),
            )
        else:
            rows = self._q(
                """SELECT e.*, c.canonical_name FROM events e
                   JOIN companies c ON e.company_id = c.id
                   ORDER BY e.event_date DESC LIMIT ?""",
                (limit,),
            )
        return [dict(r) for r in rows]

    # ── relations ─────────────────────────────────────────────────────────────

    def insert_relation(self, data: dict) -> str:
        rid = data.get("id") or str(uuid4())
        self._run(
            """INSERT INTO company_relations
               (id, company_id, related_entity_name, related_entity_type,
                relation_subtype, partner_name, board_seat, valid_from, valid_to,
                source_url, confidence)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                rid,
                data["company_id"],
                data["related_entity_name"],
                data["related_entity_type"],
                data.get("relation_subtype"),
                data.get("partner_name"),
                data.get("board_seat", False),
                data.get("valid_from"),
                data.get("valid_to"),
                data.get("source_url"),
                data.get("confidence", 0.5),
            ),
        )
        return rid

    def get_relations(self, company_id: str, relation_type: str | None = None) -> list[dict]:
        if relation_type:
            rows = self._q(
                """SELECT * FROM company_relations
                   WHERE company_id = ? AND related_entity_type = ?
                   AND (valid_to IS NULL)""",
                (company_id, relation_type),
            )
        else:
            rows = self._q(
                "SELECT * FROM company_relations WHERE company_id = ? AND (valid_to IS NULL)",
                (company_id,),
            )
        return [dict(r) for r in rows]

    def get_all_investors(self) -> list[dict]:
        rows = self._q(
            """SELECT r.related_entity_name as investor, r.relation_subtype,
                      r.board_seat, c.canonical_name as company, c.id as company_id
               FROM company_relations r JOIN companies c ON r.company_id = c.id
               WHERE r.related_entity_type = 'investor' AND (r.valid_to IS NULL)
               ORDER BY r.related_entity_name"""
        )
        return [dict(r) for r in rows]

    # ── conflicts ─────────────────────────────────────────────────────────────

    def insert_conflict(self, data: dict) -> str:
        cid = data.get("id") or str(uuid4())
        self._run(
            """INSERT INTO conflicts
               (id, company_id, field_name, existing_value, new_value,
                existing_source, new_source, existing_source_tier, new_source_tier, reason)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                cid,
                data.get("company_id"),
                data["field_name"],
                json.dumps(data.get("existing_value")),
                json.dumps(data.get("new_value")),
                data.get("existing_source"),
                data.get("new_source"),
                data.get("existing_source_tier"),
                data.get("new_source_tier"),
                data.get("reason"),
            ),
        )
        return cid

    def count_conflicts(self, status: str = "pending") -> int:
        row = self._one("SELECT COUNT(*) as n FROM conflicts WHERE status = ?", (status,))
        return row["n"] if row else 0

    def get_conflicts(self, status: str = "pending") -> list[dict]:
        rows = self._q(
            """SELECT f.*, c.canonical_name FROM conflicts f
               LEFT JOIN companies c ON f.company_id = c.id
               WHERE f.status = ? ORDER BY f.created_at DESC""",
            (status,),
        )
        return [dict(r) for r in rows]

    def resolve_conflict(self, conflict_id: str, resolution: str, resolved_value: str):
        self._run(
            """UPDATE conflicts SET status='resolved', resolution=?, resolved_value=?,
               resolved_at=? WHERE id=?""",
            (resolution, resolved_value, datetime.utcnow().isoformat(), conflict_id),
        )

    # ── candidates ────────────────────────────────────────────────────────────

    def insert_candidate(self, data: dict) -> str:
        cid = data.get("id") or str(uuid4())
        # skip if duplicate discovered_name
        existing = self._one(
            "SELECT id FROM candidate_companies WHERE discovered_name = ? AND status='pending'",
            (data.get("discovered_name", ""),),
        )
        if existing:
            return existing["id"]
        self._run(
            """INSERT INTO candidate_companies
               (id, discovered_name, discovered_url, discovery_source,
                discovery_reason, initial_evidence)
               VALUES (?,?,?,?,?,?)""",
            (
                cid,
                data.get("discovered_name", ""),
                data.get("discovered_url"),
                data.get("discovery_source", ""),
                data.get("discovery_reason"),
                json.dumps(data.get("initial_evidence", {})),
            ),
        )
        return cid

    def count_candidates(self, status: str = "pending") -> int:
        row = self._one(
            "SELECT COUNT(*) as n FROM candidate_companies WHERE status = ?", (status,)
        )
        return row["n"] if row else 0

    def get_candidates(self, status: str = "pending") -> list[dict]:
        rows = self._q(
            "SELECT * FROM candidate_companies WHERE status = ? ORDER BY created_at DESC",
            (status,),
        )
        return [dict(r) for r in rows]

    def approve_candidate(self, candidate_id: str) -> str:
        cand = self._one(
            "SELECT * FROM candidate_companies WHERE id = ?", (candidate_id,)
        )
        if not cand:
            raise ValueError(f"Candidate {candidate_id} not found")
        ev = json.loads(cand["initial_evidence"] or "{}")
        company_id = self.insert_company(
            {
                "canonical_name": cand["discovered_name"],
                "website": cand["discovered_url"],
                "status": "active",
                "confidence_score": 0.5,
                **ev,
            }
        )
        self._run(
            """UPDATE candidate_companies
               SET status='approved', merged_into_company_id=?, reviewed_at=? WHERE id=?""",
            (company_id, datetime.utcnow().isoformat(), candidate_id),
        )
        return company_id

    def reject_candidate(self, candidate_id: str, reason: str = ""):
        self._run(
            """UPDATE candidate_companies
               SET status='rejected', rejection_reason=?, reviewed_at=? WHERE id=?""",
            (reason, datetime.utcnow().isoformat(), candidate_id),
        )

    # ── digests ───────────────────────────────────────────────────────────────

    def save_digest(self, content: str, digest_type: str = "weekly", company_ids: list | None = None) -> str:
        did = str(uuid4())
        self._run(
            "INSERT INTO digests (id, digest_type, company_ids, content) VALUES (?,?,?,?)",
            (did, digest_type, json.dumps(company_ids) if company_ids else None, content),
        )
        return did

    def get_digests(self, limit: int = 10) -> list[dict]:
        rows = self._q("SELECT * FROM digests ORDER BY created_at DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]

    # ── raw signals ───────────────────────────────────────────────────────────

    def insert_raw_signal(self, data: dict) -> str:
        sid = data.get("id") or str(uuid4())
        self._run(
            """INSERT OR IGNORE INTO raw_signals
               (id, source_url, source_type, raw_content, extracted_events, related_company_ids)
               VALUES (?,?,?,?,?,?)""",
            (
                sid,
                data["source_url"],
                data.get("source_type"),
                data.get("raw_content"),
                json.dumps(data.get("extracted_events", [])),
                json.dumps(data.get("related_company_ids", [])),
            ),
        )
        return sid
