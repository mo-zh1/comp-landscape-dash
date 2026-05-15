"""
Local review server — serves the dashboard + staging review API.

Usage:
    python review_server.py          # → http://localhost:8080
    python review_server.py 9000     # custom port
"""
import json as _json
import sys
import threading
from pathlib import Path
from uuid import uuid4

from flask import Flask, abort, jsonify, request, send_from_directory

from core import config
from core.db import Database
from core.staging import StagingDB, stage_company_result
from core.resolver import resolve_company
import services

app = Flask(__name__, static_folder=str(Path(__file__).parent))

# ── in-memory job registry (probe / pipeline runs) ────────────────────────────

_jobs: dict[str, dict] = {}  # job_id → {status, ...}


def _spawn(job_id: str, fn, *args):
    def _run():
        try:
            result = fn(*args)
            _jobs[job_id].update({"status": "done", **(result or {})})
        except Exception as exc:
            _jobs[job_id].update({"status": "error", "error": str(exc)})
    t = threading.Thread(target=_run, daemon=True)
    t.start()


# ── static serving ────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/data.json")
def data_json_file():
    return send_from_directory(".", "data.json")


# ── data refresh ──────────────────────────────────────────────────────────────

def _export():
    import export
    export.run()


# ── staging read API ──────────────────────────────────────────────────────────

@app.route("/api/staging")
def api_staging():
    """
    Unified pending queue:
      • staging.db.staged_candidates — local probes & non-direct pipeline runs
      • competitors.db.candidate_companies (status='pending') — CI scans (--direct)
    De-duplicated by discovered_name (staging wins, since it has richer evidence).
    """
    s = StagingDB()
    data = s.get_pending()
    s.close()

    db = Database(config.DB_PATH)
    db.init_schema()
    seen = {c["discovered_name"] for c in data.get("candidates", [])}
    extra = [c for c in db.get_candidates("pending") if c["discovered_name"] not in seen]
    db.close()

    data["candidates"] = list(data.get("candidates", [])) + extra
    return jsonify(data)


@app.route("/api/staging/runs")
def api_staging_runs():
    s = StagingDB()
    runs = s.get_runs()
    s.close()
    return jsonify(runs)


@app.route("/api/staging/runs/<run_id>")
def api_staging_run_detail(run_id):
    s = StagingDB()
    items = s.get_run_items(run_id)
    s.close()
    return jsonify(items)


# ── staged_updates approve / reject ───────────────────────────────────────────

@app.route("/api/staging/updates/<row_id>/approve", methods=["POST"])
def approve_update(row_id):
    s = StagingDB()
    row = s.get_update(row_id)
    if not row:
        s.close()
        abort(404)

    db = Database(config.DB_PATH)
    db.init_schema()

    company_id = row["company_id"]

    # probe may stage updates for companies not yet in final DB (company_id=None)
    if not company_id and row.get("company_name"):
        existing = db._one(
            "SELECT id FROM companies WHERE canonical_name = ?", (row["company_name"],)
        )
        if existing:
            company_id = existing["id"]
        else:
            # create a minimal company record so updates have somewhere to land
            company_id = db.insert_company({
                "canonical_name": row["company_name"],
                "status": "active",
                "confidence_score": 0.5,
            })

    if company_id:
        db.update_company(company_id, {row["field_name"]: row["new_value"]})

    db.close()
    _export()  # always refresh data.json after any approve
    s.set_status("staged_updates", row_id, "approved")
    s.close()
    return jsonify({"ok": True, "company_id": company_id})


@app.route("/api/staging/updates/<row_id>/reject", methods=["POST"])
def reject_update(row_id):
    s = StagingDB()
    s.set_status("staged_updates", row_id, "rejected")
    s.close()
    return jsonify({"ok": True})


# ── staged_events approve / reject ────────────────────────────────────────────

@app.route("/api/staging/events/<row_id>/approve", methods=["POST"])
def approve_event(row_id):
    s = StagingDB()
    row = s.get_event(row_id)
    if not row:
        s.close()
        abort(404)
    if row["company_id"] and row["fingerprint"]:
        db = Database(config.DB_PATH)
        db.init_schema()
        if not db.get_event_by_fingerprint(row["fingerprint"]):
            payload = row["payload"]
            if isinstance(payload, str):
                try:
                    payload = _json.loads(payload)
                except Exception:
                    payload = {}
            db.insert_event({
                "company_id":  row["company_id"],
                "event_type":  row["event_type"],
                "event_date":  row["event_date"],
                "payload":     payload,
                "fingerprint": row["fingerprint"],
                "source_url":  row["source_url"],
                "source_tier": row["source_tier"],
                "confidence":  row["confidence"],
            })
            _export()
        db.close()
    s.set_status("staged_events", row_id, "approved")
    s.close()
    return jsonify({"ok": True})


@app.route("/api/staging/events/<row_id>/reject", methods=["POST"])
def reject_event(row_id):
    s = StagingDB()
    s.set_status("staged_events", row_id, "rejected")
    s.close()
    return jsonify({"ok": True})


# ── staged_candidates approve / reject ────────────────────────────────────────

@app.route("/api/staging/candidates/<row_id>/approve", methods=["POST"])
def approve_candidate(row_id):
    """
    Approve from either source:
      • staging.db row → copy into final DB, then promote.
      • final-DB row (CI scan) → promote in place.
    """
    s  = StagingDB()
    db = Database(config.DB_PATH)
    db.init_schema()

    row = s.get_candidate(row_id)
    if row:
        evidence = row.get("initial_evidence") or "{}"
        if isinstance(evidence, str):
            try:
                evidence = _json.loads(evidence)
            except Exception:
                evidence = {}
        cid = db.insert_candidate({
            "discovered_name":  row["discovered_name"],
            "discovered_url":   row["discovered_url"],
            "discovery_source": row["discovery_source"] or "",
            "discovery_reason": row["discovery_reason"],
            "initial_evidence": evidence,
        })
        db.approve_candidate(cid)
        s.set_status("staged_candidates", row_id, "approved")
    else:
        try:
            db.approve_candidate(row_id)
        except ValueError:
            db.close(); s.close(); abort(404)

    _export()
    db.close()
    s.close()
    return jsonify({"ok": True})


@app.route("/api/staging/candidates/<row_id>/reject", methods=["POST"])
def reject_candidate(row_id):
    s = StagingDB()
    if s.get_candidate(row_id):
        s.set_status("staged_candidates", row_id, "rejected")
    else:
        db = Database(config.DB_PATH)
        db.init_schema()
        db.reject_candidate(row_id)
        db.close()
    s.close()
    return jsonify({"ok": True})


# ── probe API (async) ─────────────────────────────────────────────────────────

def _do_probe(job_id: str, company: str, website: str | None, linkedin: str | None):
    db = Database(config.DB_PATH)
    db.init_schema()
    s = StagingDB()
    run_id = s.start_run("probe")
    result = services.scrape_competitor(company, website, linkedin)
    company_id, conf, method = resolve_company(company, website, linkedin, None, None, db)
    stage_company_result(s, db, run_id, company_id, company, result)
    s.finish_run(run_id, "done", {"company": company, "confidence": conf})
    s.close()
    db.close()
    return {"run_id": run_id, "matched_id": company_id, "confidence": conf}


@app.route("/api/probe", methods=["POST"])
def api_probe():
    body = request.get_json() or {}
    company = (body.get("company") or "").strip()
    if not company:
        abort(400)
    job_id = uuid4().hex[:12]
    _jobs[job_id] = {"status": "running"}
    _spawn(job_id, _do_probe, job_id, company,
           body.get("website"), body.get("linkedin"))
    return jsonify({"job_id": job_id})


@app.route("/api/probe/<job_id>")
def api_probe_status(job_id):
    return jsonify(_jobs.get(job_id, {"status": "not_found"}))


# ── pipeline run API (async) ──────────────────────────────────────────────────

def _do_run(job_id: str, trigger: str):
    from pipeline import scan_run, weekly_run, digest_run
    db = Database(config.DB_PATH)
    db.init_schema()
    s = StagingDB()

    progress: list[dict] = _jobs[job_id]["progress"]

    if trigger == "scan":
        scan_run(db, s)
    elif trigger == "weekly":
        weekly_run(db, s, on_progress=progress.append)
    elif trigger == "digest":
        digest_run(db)

    s.close()
    db.close()
    _export()
    return {}


@app.route("/api/run", methods=["POST"])
def api_run():
    body = request.get_json() or {}
    trigger = body.get("trigger", "")
    if trigger not in ("scan", "weekly", "digest"):
        abort(400)
    job_id = uuid4().hex[:12]
    _jobs[job_id] = {"status": "running", "trigger": trigger, "progress": []}
    _spawn(job_id, _do_run, job_id, trigger)
    return jsonify({"job_id": job_id})


@app.route("/api/run/<job_id>")
def api_run_status(job_id):
    return jsonify(_jobs.get(job_id, {"status": "not_found"}))


# ── on-demand digest API (async) ──────────────────────────────────────────────

def _do_digest(job_id: str, company_ids: list | None):
    from pipeline import digest_run
    db = Database(config.DB_PATH)
    db.init_schema()
    if company_ids:
        events    = db.get_events_since(days=30)
        companies = db.get_companies()
        md = services.generate_digest(events, companies, company_ids=company_ids)
        digest_id = db.save_digest(md, "on_demand", company_ids)
    else:
        md = digest_run(db)
        digest_id = None
    _export()
    db.close()
    return {"content": md, "digest_id": digest_id}


@app.route("/api/digest", methods=["POST"])
def api_digest():
    body = request.get_json() or {}
    company_ids = body.get("company_ids") or None   # list or None
    job_id = uuid4().hex[:12]
    _jobs[job_id] = {"status": "running"}
    _spawn(job_id, _do_digest, job_id, company_ids)
    return jsonify({"job_id": job_id})


@app.route("/api/digest/<job_id>")
def api_digest_status(job_id):
    return jsonify(_jobs.get(job_id, {"status": "not_found"}))


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print(f"\nReview server → http://localhost:{port}\n")
    app.run(port=port, debug=False, threaded=True)
