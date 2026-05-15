"""Entity resolution, event fingerprinting, and SCD field updates."""
import hashlib
import json
from datetime import date, timedelta
from urllib.parse import urlparse

from rapidfuzz import fuzz

from .db import Database

# ── source tier mapping ───────────────────────────────────────────────────────

_DOMAIN_TIERS: dict[str, tuple[str, int]] = {
    "techcrunch.com": ("techcrunch", 2),
    "betakit.com": ("betakit", 2),
    "businesswire.com": ("businesswire", 2),
    "prnewswire.com": ("prnewswire", 2),
    "globenewswire.com": ("globenewswire", 2),
    "mining.com": ("mining_com", 2),
    "australianmining.com.au": ("australian_mining", 2),
    "miningbeacon.com": ("mining_beacon", 2),
    "globalminingreview.com": ("global_mining_review", 2),
    "crunchbase.com": ("crunchbase_funding", 2),
    "pitchbook.com": ("pitchbook", 3),
    "linkedin.com": ("linkedin", 3),
    "tracxn.com": ("tracxn", 4),
    "cbinsights.com": ("cbinsights", 4),
    "zoominfo.com": ("zoominfo", 4),
    "rocketreach.com": ("rocketreach", 4),
}


def classify_source(url: str) -> tuple[str, int]:
    """Return (source_type, tier) for a URL."""
    try:
        domain = urlparse(url).netloc.lstrip("www.")
    except Exception:
        return ("unknown", 3)
    for key, val in _DOMAIN_TIERS.items():
        if domain.endswith(key):
            return val
    # assume company website = tier 1
    return ("company_website", 1)


def extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lstrip("www.").lower()
    except Exception:
        return ""


# ── entity resolution ─────────────────────────────────────────────────────────

def resolve_company(
    name: str,
    url: str | None,
    linkedin: str | None,
    hq: str | None,
    founders: list[str] | None,
    db: Database,
) -> tuple[str | None, float, str]:
    """
    Returns (matched_company_id, confidence, match_method).
    confidence > 0.95 → auto-merge
    0.85-0.95 → auto-merge + flag review
    0.7-0.85 → conflict queue
    < 0.7 → new candidate
    """
    # Layer 1: deterministic
    if url:
        domain = extract_domain(url)
        if domain:
            match = db.get_company_by_website(domain)
            if match:
                return (match["id"], 1.0, "domain_match")

    if linkedin:
        row = db._one(
            "SELECT id FROM companies WHERE linkedin_url = ?", (linkedin,)
        )
        if row:
            return (row["id"], 1.0, "linkedin_match")

    # Layer 2: fuzzy name match
    candidates = db.get_companies()
    best_score = 0.0
    best_id = None

    for c in candidates:
        name_score = fuzz.token_sort_ratio(name.lower(), c["canonical_name"].lower()) / 100

        if name_score > 0.85 and hq and c.get("hq_city"):
            city_score = fuzz.ratio(hq.lower(), c["hq_city"].lower()) / 100
            if city_score > 0.8:
                combined = (name_score + 0.95) / 2
                if combined > best_score:
                    best_score = combined
                    best_id = c["id"]

        if name_score > 0.90 and name_score > best_score:
            best_score = name_score
            best_id = c["id"]

    if best_score > 0.70:
        return (best_id, best_score, "fuzzy_match")

    return (None, 0.0, "no_match")


# ── event fingerprint ─────────────────────────────────────────────────────────

_BUCKET_DAYS: dict[str, int] = {
    "funding_round": 7,
    "acquisition": 7,
    "leadership_change": 30,
    "product_launch": 1,
    "partnership": 7,
    "customer_win": 30,
    "customer_loss": 30,
    "hiring_signal": 30,
    "tech_disclosure": 7,
    "pivot": 30,
    "rebrand": 30,
}


def event_fingerprint(
    company_id: str, event_type: str, event_date: date, payload: dict
) -> str:
    bucket_size = _BUCKET_DAYS.get(event_type, 7)
    bucket = event_date.toordinal() // bucket_size

    if event_type == "funding_round":
        amount = payload.get("amount_usd", 0) or 0
        amount_bucket = round(amount / 100_000)
        key = f"{payload.get('round_type', 'unknown')}_{amount_bucket}"
    elif event_type == "acquisition":
        key = (payload.get("target_name") or payload.get("acquirer_name") or "").lower().strip()
    elif event_type == "leadership_change":
        person = (payload.get("person_name") or "").lower().strip()
        role = (payload.get("role") or "").lower().strip()
        key = f"{person}_{role}"
    else:
        key = hashlib.md5(
            json.dumps(sorted(payload.items()), default=str).encode()
        ).hexdigest()[:8]

    raw = f"{company_id}|{event_type}|{bucket}|{key}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ── SCD field update ──────────────────────────────────────────────────────────

_SCD_STRATEGY: dict[str, str] = {
    "founded_year": "type1",
    "last_updated": "type1",
    "hq_city": "type1",
    "hq_country": "type1",
    "confidence_score": "type1",
    "canonical_name": "type2",
    "website": "type2",
    "target_customer": "type2",
    "core_product": "type2",
    "pricing_model": "type2",
    "business_model_summary": "type2",
    "status": "type2",
    "latest_round_type": "type4",
    "latest_round_amount_usd": "type4",
    "latest_round_date": "type4",
}


def update_field(
    company_id: str,
    field_name: str,
    new_value,
    new_source_url: str,
    new_source_tier: int,
    new_confidence: float,
    db: Database,
) -> str:
    """
    Returns: 'no_change' | 'updated' | 'conflict_flagged'
    """
    strategy = _SCD_STRATEGY.get(field_name, "type1")
    company = db.get_company(company_id)
    if not company:
        return "no_change"

    existing_value = company.get(field_name)

    if existing_value == new_value:
        return "no_change"

    auto_accept = False

    if existing_value is None or existing_value == "":
        auto_accept = True
    elif new_source_tier < 2:  # tier 1 always wins
        auto_accept = True
    elif new_confidence > 0.85:
        auto_accept = True

    if not auto_accept:
        db.insert_conflict(
            {
                "company_id": company_id,
                "field_name": field_name,
                "existing_value": existing_value,
                "new_value": new_value,
                "existing_source": company.get("website"),
                "new_source": new_source_url,
                "new_source_tier": new_source_tier,
                "reason": "auto-resolve rules unmet",
            }
        )
        return "conflict_flagged"

    if strategy == "type1":
        db.update_company(company_id, {field_name: new_value})

    elif strategy in ("type2", "type4"):
        if existing_value:
            fp = event_fingerprint(
                company_id,
                f"{field_name}_change",
                date.today(),
                {"old": existing_value, "new": new_value},
            )
            existing_ev = db.get_event_by_fingerprint(fp)
            if not existing_ev:
                db.insert_event(
                    {
                        "company_id": company_id,
                        "event_type": f"{field_name}_change",
                        "event_date": date.today().isoformat(),
                        "payload": {"old": existing_value, "new": new_value},
                        "fingerprint": fp,
                        "source_url": new_source_url,
                        "source_tier": new_source_tier,
                        "confidence": new_confidence,
                    }
                )
        db.update_company(company_id, {field_name: new_value})

    return "updated"


def merge_scraped_company(db: Database, company_id: str, scraped: dict):
    """Apply a scrape_competitor result to an existing company record."""
    field_map = {
        "website": ("website", 1),
        "founded_year": ("founded_year", 1),
        "hq_city": ("hq_city", 2),
        "hq_country": ("hq_country", 2),
        "target_customer": ("target_customer", 2),
        "core_product": ("core_product", 2),
        "pricing_model": ("pricing_model", 2),
        "business_model_summary": ("business_model_summary", 2),
    }

    source_url = scraped.get("sources", [{}])[0].get("url", "") if scraped.get("sources") else ""
    source_tier = 2

    for scraped_key, (db_field, default_tier) in field_map.items():
        val = scraped.get(scraped_key)
        if val is None:
            continue
        conf = scraped.get("confidence_per_field", {}).get(scraped_key, 0.5)
        update_field(company_id, db_field, val, source_url, default_tier, conf, db)

    # latest round
    lr = scraped.get("latest_round")
    if lr and lr.get("type"):
        for fld, scraped_fld in [
            ("latest_round_type", "type"),
            ("latest_round_amount_usd", "amount_usd"),
            ("latest_round_date", "date"),
        ]:
            v = lr.get(scraped_fld)
            if v is not None:
                update_field(company_id, fld, v, source_url, source_tier, 0.8, db)

    # insert funding_round event if new
    if lr and lr.get("type") and lr.get("date"):
        try:
            ev_date = date.fromisoformat(lr["date"][:10])
        except Exception:
            ev_date = date.today()
        fp = event_fingerprint(company_id, "funding_round", ev_date, lr)
        if not db.get_event_by_fingerprint(fp):
            db.insert_event(
                {
                    "company_id": company_id,
                    "event_type": "funding_round",
                    "event_date": ev_date.isoformat(),
                    "payload": lr,
                    "fingerprint": fp,
                    "source_url": lr.get("source_url") or source_url,
                    "source_tier": source_tier,
                    "confidence": 0.8,
                }
            )

    # relations: investors
    for inv in scraped.get("investors", []):
        name = inv.get("name", "")
        if not name:
            continue
        existing = db._q(
            """SELECT id FROM company_relations
               WHERE company_id=? AND related_entity_name=? AND related_entity_type='investor'
               AND valid_to IS NULL""",
            (company_id, name),
        )
        if not existing:
            db.insert_relation(
                {
                    "company_id": company_id,
                    "related_entity_name": name,
                    "related_entity_type": "investor",
                    "relation_subtype": inv.get("role"),
                    "source_url": source_url,
                    "confidence": 0.7,
                }
            )
