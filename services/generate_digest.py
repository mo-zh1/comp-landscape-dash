"""
Service 4 — generate_digest
Input : events[], companies[], conflicts_pending, candidates_pending
        company_ids: optional list of company IDs → on-demand mode
Output: Markdown string

On-demand mode (company_ids set):
  Part A — Recent activity + LLM summary per company
  Part B — Comparative analysis across selected companies
"""
import json
import textwrap
from datetime import date

from services.utils import llm


def run(
    events: list[dict],
    companies: list[dict],
    conflicts_pending: int = 0,
    candidates_pending: int = 0,
    company_ids: list[str] | None = None,
) -> str:
    if company_ids:
        return _on_demand(events, companies, company_ids)
    return _weekly(events, companies, conflicts_pending, candidates_pending)


# ── weekly digest ──────────────────────────────────────────────────────────

def _weekly(
    events: list[dict],
    companies: list[dict],
    conflicts_pending: int,
    candidates_pending: int,
) -> str:
    if not events and not candidates_pending and not conflicts_pending:
        return (
            f"# Competitive Intelligence Weekly — {date.today().strftime('Week %W, %Y')}\n\n"
            "No new signals this week.\n"
        )

    events_text = "\n".join(_fmt(e) for e in events[:50])
    companies_text = "\n".join(
        f"- {c['canonical_name']} ({c.get('status', 'active')}) — {c.get('latest_round_type', 'N/A')}"
        for c in companies
    )

    prompt = textwrap.dedent(f"""
        Write a CEO weekly competitive intelligence briefing.

        Week: {date.today().strftime("Week %W, %Y")} (through {date.today().isoformat()})
        Tracked companies ({len(companies)}): {companies_text}

        Events this week ({len(events)} total):
        {events_text}

        Admin: {conflicts_pending} conflicts pending, {candidates_pending} new candidates pending.

        Format (exact Markdown structure):

        # Competitive Intelligence Weekly — Week N, YYYY

        ## High-Priority Events
        (funding rounds, acquisitions, leadership changes — each with "So what:" analysis)

        ## Partnerships & Customers

        ## Team & Hiring

        ## New Competitor Signals
        ({candidates_pending} candidates pending approval)

        ## Action Items
        - {conflicts_pending} conflicts pending review
        - {candidates_pending} candidates pending approval

        Rules: "So what:" must be specific and actionable. Max 600 words total.
    """).strip()

    return llm(prompt, max_tokens=1500)


# ── on-demand digest ───────────────────────────────────────────────────────

def _on_demand(
    events: list[dict],
    companies: list[dict],
    company_ids: list[str],
) -> str:
    id_set = set(company_ids)
    sel_companies = [c for c in companies if c.get("id") in id_set]
    sel_events    = [e for e in events    if e.get("company_id") in id_set]

    if not sel_companies:
        return "# On-Demand Digest\n\nNo matching companies found.\n"

    names = ", ".join(c["canonical_name"] for c in sel_companies)

    # Part A — recent activity per company
    activity_lines: list[str] = []
    for c in sel_companies:
        co_events = [e for e in sel_events if e.get("company_id") == c.get("id")]
        ev_text = "\n".join(f"  - {e.get('event_date','?')} | {e.get('event_type','?')} | {_fmt_payload(e)}"
                            for e in co_events[:10]) or "  (no recent events)"
        activity_lines.append(
            f"Company: {c['canonical_name']}\n"
            f"Website: {c.get('website') or '—'}\n"
            f"Stage: {c.get('latest_round_type') or '—'} · {c.get('latest_round_text') or '—'}\n"
            f"Business model: {c.get('business_model_summary') or '—'}\n"
            f"Technical: {c.get('technical') or '—'}\n"
            f"Events:\n{ev_text}"
        )

    activity_block = "\n\n".join(activity_lines)

    # Part B — comparative profile block
    compare_fields = ["canonical_name", "hq_country", "founded_year",
                      "core_product", "stage_focus", "latest_round_type",
                      "latest_round_text", "investors_text", "valuation",
                      "target_customer", "technical"]
    profiles = []
    for c in sel_companies:
        p = {f: c.get(f) for f in compare_fields if c.get(f)}
        profiles.append(json.dumps(p, ensure_ascii=False))
    compare_block = "\n".join(profiles)

    prompt = textwrap.dedent(f"""
        Generate an on-demand competitive intelligence digest for {len(sel_companies)} selected companies.
        Date: {date.today().isoformat()}
        Companies: {names}

        === ACTIVITY DATA ===
        {activity_block}

        === COMPANY PROFILES ===
        {compare_block}

        Format (exact Markdown):

        # On-Demand Digest: {names}
        *Generated {date.today().isoformat()}*

        ## Part A — Recent Activity

        (For each company: 2–3 sentence summary of recent events and key signals.
        If no events, describe their current known status from the profile.)

        ## Part B — Comparative Analysis

        ### Funding & Stage
        (Compare their funding stages, amounts, and trajectory)

        ### Technology & Product
        (Compare their core technical approaches and product differentiation)

        ### Target Market & Positioning
        (Compare who they sell to and how they compete)

        ### Key Risks & Opportunities
        (Identify where each is strong/weak relative to the others)

        ### Summary Table
        | Company | Stage | Tech | Market | Notable |
        |---------|-------|------|--------|---------|
        (one row per company)

        Rules: Be specific, cite actual data. "So what:" framing for every insight.
        Max 800 words total.
    """).strip()

    return llm(prompt, max_tokens=2000)


# ── helpers ────────────────────────────────────────────────────────────────

def _fmt(e: dict) -> str:
    payload = e.get("payload", "{}")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}
    name = e.get("canonical_name", "Unknown")
    return f"{e.get('event_date', '?')} | {name} | {e.get('event_type', '?')} | {_fmt_payload(e)}"


def _fmt_payload(e: dict) -> str:
    payload = e.get("payload", {})
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            return ""
    return json.dumps(payload)[:100] if payload else ""
