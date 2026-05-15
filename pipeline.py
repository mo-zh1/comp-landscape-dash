"""
Orchestrator — run with:
  python pipeline.py seed        # first-time setup
  python pipeline.py scan        # scan curated sources → candidate pre-screening queue
  python pipeline.py weekly      # deep-scrape all approved companies
  python pipeline.py digest      # generate weekly markdown digest (saved to DB)
  python pipeline.py probe       # one-off scrape of a single company
"""
import argparse
import json
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from core import config
from core.db import Database
from core.resolver import classify_source, merge_scraped_company, resolve_company
from core.staging import StagingDB, stage_company_result
import services


# ── pipeline stages ───────────────────────────────────────────────────────────

def scan_run(db: Database, staging_db: StagingDB | None = None):
    """Scan curated sources; stage candidate companies for human pre-screening."""
    print("--- SCAN RUN ---")
    run_id = staging_db.start_run("scan") if staging_db else None

    known_names = [c["canonical_name"] for c in db.get_companies()]
    result = services.scan_sources(known_companies=known_names)

    for cand in result.get("candidates", []):
        name = cand.get("name", "").strip()
        if not name:
            continue
        if staging_db:
            staging_db.insert_candidate(
                run_id, name,
                cand.get("website"),
                cand.get("source_url", ""),
                cand.get("summary", ""),
                {"signals": cand.get("signals")},
            )
        else:
            db.insert_candidate({
                "discovered_name":  name,
                "discovered_url":   cand.get("website"),
                "discovery_source": cand.get("source_url", ""),
                "discovery_reason": cand.get("summary", ""),
                "initial_evidence": {"signals": cand.get("signals")},
            })
        print(f"  + candidate: {name}")

    if staging_db:
        staging_db.finish_run(run_id, "done", {"candidates": len(result.get("candidates", []))})
    print("  done.")


def weekly_run(db: Database, staging_db: StagingDB | None = None, on_progress=None):
    """Deep-scrape every active company; merge or stage field updates."""
    print("--- WEEKLY RUN ---")
    run_id = staging_db.start_run("weekly") if staging_db else None
    errors: list[dict] = []

    for c in db.get_companies(status="active"):
        name = c["canonical_name"]
        print(f"  scraping: {name}")
        try:
            result = services.scrape_competitor(name, c.get("website"), c.get("linkedin_url"))

            if result.get("_error"):
                raise RuntimeError(result["_error"])

            for page_url, html in result.get("raw_pages", {}).items():
                db.insert_raw_signal({
                    "source_url": page_url,
                    "source_type": classify_source(page_url)[0],
                    "raw_content": html,
                    "related_company_ids": [c["id"]],
                })

            if staging_db:
                stage_company_result(staging_db, db, run_id, c["id"], name, result)
            else:
                merge_scraped_company(db, c["id"], result)

            db.update_company(c["id"], {
                "last_scrape_error": None,
                "last_scraped_at": datetime.utcnow().isoformat(),
            })
            if on_progress:
                on_progress({"company": name, "status": "ok"})

        except Exception as e:
            err_msg = str(e)
            errors.append({"company": name, "error": err_msg})
            db.update_company(c["id"], {"last_scrape_error": err_msg})
            print(f"    ✗ {name}: {err_msg}")
            if on_progress:
                on_progress({"company": name, "status": "error", "error": err_msg})

    if staging_db:
        staging_db.finish_run(run_id, "done", {"errors": errors})
    print(f"  done. ({len(errors)} error(s))")


def digest_run(db: Database) -> str:
    """Generate weekly digest markdown; save to digests table and digests/ folder."""
    print("--- DIGEST RUN ---")
    events     = db.get_events_since(days=7)
    companies  = db.get_companies()
    conflicts  = db.count_conflicts("pending")
    candidates = db.count_candidates("pending")
    print(f"  {len(events)} events · {conflicts} conflicts · {candidates} candidates")

    digest_md = services.generate_digest(events, companies, conflicts, candidates)

    # persist to DB
    db.save_digest(digest_md, "weekly")

    # also write to file for git tracking
    out = Path("digests") / f"week-{date.today().strftime('%Y-%W')}.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(digest_md)
    print(f"  saved: {out}")
    return digest_md


# ── probe (single-company dry run) ────────────────────────────────────────────

def probe_run(db: Database, company: str, website: str | None, linkedin: str | None):
    """Scrape one company, diff vs DB, stage results, write probe_output.json."""
    print(f"\n=== PROBE: {company} ===")
    print("  scraping (takes ~30–60 s)…")

    result = services.scrape_competitor(company, website, linkedin)

    company_id, conf, method = resolve_company(company, website, linkedin, None, None, db)
    existing = db.get_company(company_id) if company_id else {}

    print(f"  matched : {existing.get('canonical_name') or 'no match'}"
          f"  (conf {conf:.0%}, {method})")
    print("  scraped fields:")
    for field in ["hq_city", "hq_country", "founded_year", "core_product",
                  "pricing_model", "target_customer", "business_model_summary"]:
        val = result.get(field)
        if val:
            old = existing.get(field)
            marker = "~" if old and str(old) != str(val) else "+"
            print(f"    {marker} {field}: {str(val)[:80]}")

    lr = result.get("latest_round")
    if lr and lr.get("type"):
        print(f"  latest round: {lr.get('type')} · "
              f"{lr.get('amount_usd')} · {lr.get('date')}")

    staging_db = StagingDB()
    run_id = staging_db.start_run("probe")
    stage_company_result(staging_db, db, run_id, company_id, company, result)
    staging_db.finish_run(run_id, "done", {"company": company})
    staging_db.close()

    output = {
        "company": company,
        "website": website,
        "matched_company_id": company_id,
        "match_confidence": conf,
        "match_method": method,
        "staged_run_id": run_id,
        "scraped": {k: v for k, v in result.items() if k != "raw_pages"},
    }
    Path("probe_output.json").write_text(
        json.dumps(output, indent=2, default=str)
    )
    print(f"\n  staged to : staging.db  (run_id: {run_id})")
    print(f"  written to: probe_output.json")
    print(f"  review at : python review_server.py  →  http://localhost:8080")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Competitor Intel Pipeline")
    parser.add_argument(
        "trigger",
        choices=["seed", "scan", "weekly", "digest", "probe"],
    )
    parser.add_argument("--db",       default=None, help="Override DB path")
    parser.add_argument("--company",  default=None, help="Company name (probe mode)")
    parser.add_argument("--website",  default=None, help="Website URL (probe mode)")
    parser.add_argument("--linkedin", default=None, help="LinkedIn URL (probe mode)")
    parser.add_argument(
        "--direct", action="store_true",
        help="Write directly to final DB, bypassing staging",
    )
    args = parser.parse_args()

    if args.trigger == "seed":
        from core import seed
        seed.run()
        return

    db = Database(args.db or config.DB_PATH)
    db.init_schema()

    if args.trigger == "probe":
        if not args.company:
            parser.error("probe requires --company")
        probe_run(db, args.company, args.website, args.linkedin)
        db.close()
        return

    staging_db = None if args.direct else StagingDB()

    if args.trigger == "digest":
        digest_run(db)
    elif args.trigger == "scan":
        scan_run(db, staging_db)
    elif args.trigger == "weekly":
        weekly_run(db, staging_db)

    if staging_db:
        staging_db.close()
    db.close()


if __name__ == "__main__":
    main()
