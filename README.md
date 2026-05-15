# Competitive Landscape Dashboard

Automated pipeline that tracks **mining / subsurface AI startups**: scans curated sources weekly, deep-scrapes approved companies with Claude, stages changes for human review, and publishes an auto-updating dashboard to Vercel.

---

## Architecture

```
┌──────────────────────────────────────────┐
│  SCHEDULER  (.github/workflows/weekly.yml)│
│  Sunday 14:00 UTC cron                   │
└──────────────┬───────────────────────────┘
               │ triggers
               ▼
┌──────────────────────────────────────────┐
│  ORCHESTRATOR  (pipeline.py)             │
│  scan → weekly → digest → export        │
└──────────────┬───────────────────────────┘
               │ calls
               ▼
┌──────────────────────────────────────────┐
│  SERVICES  (services/)                   │
│  scan_sources      → candidate list      │
│  scrape_competitor → company profile     │
│  generate_digest   → markdown report     │
└──────────────┬───────────────────────────┘
               │ reads / writes
               ▼
┌──────────────────────────────────────────┐
│  CORE  (core/)                           │
│  db        → SQLite CRUD                 │
│  resolver  → entity resolution + SCD     │
│  staging   → human-review buffer         │
│  seed      → initial company data        │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│  DASHBOARD  (index.html + data.json)     │
│  Companies · Events · Investors          │
│  Digests · Review / Ops                  │
└──────────────────────────────────────────┘
```

---

## Project Structure

```
comp-landscape-dash/
│
├── pipeline.py          ← CLI orchestrator (seed / scan / weekly / digest / probe)
├── export.py            ← DB → data.json snapshot (called by CI and review server)
├── review_server.py     ← Local Flask server: dashboard + staging review API
│
├── index.html           ← Single-page dashboard (vanilla JS, reads data.json)
├── data.json            ← Auto-generated snapshot, committed by CI → Vercel
├── vercel.json          ← Static deploy config
│
├── core/                ← Data layer (pure Python, no external calls)
│   ├── config.py        ← All settings (API keys, thresholds, DB path)
│   ├── db.py            ← SQLite wrapper + CRUD helpers
│   ├── schema.sql       ← Database schema (applied via db.init_schema())
│   ├── resolver.py      ← Entity resolution, event fingerprints, SCD field updates
│   ├── staging.py       ← staging.db buffer for human review before final merge
│   └── seed.py          ← One-time seed: 11 known companies with full profiles
│
├── services/            ← External I/O + LLM services (pure functions, no DB access)
│   ├── utils.py         ← Shared: Anthropic client, web_search (Serper), fetch_page
│   ├── scan_sources.py  ← Weekly source scan → candidate company list
│   ├── scrape_competitor.py ← Deep company profile extraction via LLM
│   └── generate_digest.py   ← Weekly CEO-style markdown digest
│
├── .github/workflows/
│   └── weekly.yml       ← Sunday cron: scan → weekly → digest → export → commit
│
├── docs/                ← Reference documents and seed CSV (not in pipeline)
│   ├── competitor_intel_pipeline_spec.md
│   ├── competitor_discovery.md
│   ├── datasource_mapping.md
│   ├── digestAndmergeInfos.md
│   └── Mohan Competitive Landscape Tracker - Sheet2.csv
│
├── competitors.db       ← Production SQLite database (committed by CI)
├── staging.db           ← Review buffer (local only, gitignored)
├── requirements.txt
├── .env.example         ← Copy to .env and fill in API keys
└── digests/             ← Auto-generated weekly markdown reports (committed by CI)
```

**Key design rule:** `services/` are pure functions (input → output). All DB reads/writes happen in `pipeline.py`, `resolver.py`, and `review_server.py`. Services never touch the DB directly.

---

## Quick Start

### 1. Clone & install

```bash
git clone <your-repo>
cd comp-landscape-dash
pip install -r requirements.txt
```

### 2. Set API keys

```bash
cp .env.example .env
```

Edit `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...   # required — all LLM calls
SERPER_API_KEY=...              # optional but recommended — enables web search sources
```

Get keys:
- Anthropic: [console.anthropic.com](https://console.anthropic.com)
- Serper: [serper.dev](https://serper.dev) (free tier available)

### 3. Seed the database

```bash
python pipeline.py seed
```

Inserts 11 known companies (Terra AI, GeologicAI, Fleet Space, etc.) with founders, investors, and funding events.

### 4. Run the local review server

```bash
python review_server.py       # → http://localhost:8080
```

The dashboard loads `data.json` for the read-only view. The **Review / Ops** tab uses live Flask APIs to run pipeline stages, probe companies, and approve/reject staged changes.

### 5. Deploy to Vercel (static view)

```bash
vercel --prod
```

Or connect the repo in the Vercel dashboard. Each CI run commits an updated `data.json`, which triggers an automatic redeploy.

---

## Running the Pipeline Manually

```bash
# Scan curated sources → candidate pre-screening queue
python pipeline.py scan

# Deep-scrape all active companies → staged field updates
python pipeline.py weekly

# Generate weekly digest → saved to DB + digests/week-YYYY-WW.md
python pipeline.py digest

# Probe a single company (dry-run: stage results, write probe_output.json)
python pipeline.py probe --company "Terra AI" --website https://terraai.com

# Apply directly to production DB without staging (used by CI)
python pipeline.py scan --direct
```

---

## Scan Sources: Current Status

The `scan` stage hits 7 sources weekly. Serper-dependent sources require `SERPER_API_KEY` in `.env`.

| # | Source | Status | Notes |
|---|--------|--------|-------|
| 1 | Cathay Innovation Medium (RSS) | ✅ Working | No key required |
| 2 | Mining.com (Serper) | ⚠️ Requires key | `SERPER_API_KEY` must be set |
| 3 | BHP Ventures (Serper) | ⚠️ Requires key | Direct page is bot-protected; uses Serper fallback |
| 4 | Rio Tinto Ventures (Serper) | ⚠️ Requires key | Old direct URL is 404; uses Serper fallback |
| 5 | Techstars Mining (Serper) | ⚠️ Requires key | `SERPER_API_KEY` must be set |
| 6 | arXiv geo-ph + cs.LG | ✅ Working | No key required |
| 7 | LinkedIn Mining AI (Serper) | ⚠️ Requires key | `SERPER_API_KEY` must be set |

**Without `SERPER_API_KEY`**, only sources 1 and 6 (Cathay RSS + arXiv) produce results. All failures are now logged explicitly rather than silently skipped.

---

## Open Issues / TODO

### Data Sources

- [ ] **Serper API key** — register at [serper.dev](https://serper.dev), add `SERPER_API_KEY` to `.env` and to GitHub Secrets; unlocks 5 of 7 scan sources
- [ ] **BHP Ventures direct scrape** — `bhp.com/what-we-do/bhp-ventures` refuses direct HTTP connections (bot protection); Serper fallback is active but shallow. Consider a headless browser approach (Playwright/Puppeteer) or a dedicated proxy for richer portfolio data
- [ ] **Rio Tinto Ventures URL** — `riotinto.com/en/about/innovation/rt-ventures` returns 404; locate the updated URL or replace with a Crunchbase/PitchBook search
- [ ] **arXiv yields papers, not companies** — the geo-ph + cs.LG feed surfaces academic work; company signal is low. Consider supplementing with dedicated VC/accelerator feeds (Y Combinator, Breakthrough Energy Ventures, DCVC)

### Infrastructure

- [ ] **Manual pipeline trigger via GitHub Actions** — expose `workflow_dispatch` inputs so any pipeline stage (`scan`, `weekly`, `digest`, `probe`) can be triggered directly from the GitHub Actions UI or via the REST API (`POST /repos/{owner}/{repo}/actions/workflows/{id}/dispatches`) without requiring a local environment. Useful for ad-hoc re-scans and one-off company probes in production.

- [ ] **Migrate to a cloud database for live dashboard interactivity** — the current architecture writes `data.json` to the repo on each CI run and serves it as a static file; the dashboard has no write path from the browser. Migrating to a hosted Postgres instance (e.g. Supabase) would enable: real-time data without a CI commit round-trip, the review/approval workflow running against the live DB from any browser (removing the dependency on `review_server.py` running locally), row-level security for multi-user access, and a stable API surface for future integrations. The placeholders `SUPABASE_URL` / `SUPABASE_KEY` in `core/config.py` mark where the `core/db.py` SQLite adapter would be swapped out.

---

## API Keys

| Key | Required | Where to get | Used for |
|-----|----------|--------------|----------|
| `ANTHROPIC_API_KEY` | **Yes** | [console.anthropic.com](https://console.anthropic.com) | All LLM calls (scrape, digest, extraction) |
| `SERPER_API_KEY` | Recommended | [serper.dev](https://serper.dev) | Web search in scan + scrape services |

---

## CI / CD

The `weekly.yml` workflow runs every Sunday at 14:00 UTC:

```
scan --direct → weekly --direct → digest --direct → export → commit DB + data.json + digests/
```

Add `ANTHROPIC_API_KEY` and `SERPER_API_KEY` as **Repository Secrets** in GitHub → Settings → Secrets → Actions.

---

## Configuration Reference (`core/config.py`)

All tunable settings live in `core/config.py`. Override any value via environment variable.

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_MODEL` | `claude-opus-4-7` | LLM model for all services |
| `DB_PATH` | `competitors.db` | SQLite file path |
| `AUTO_MERGE_HIGH` | `0.95` | Entity match confidence → silent merge |
| `AUTO_MERGE_LOW` | `0.85` | Entity match confidence → merge + flag review |
| `CONFLICT_FLOOR` | `0.70` | Below this → push to conflicts queue |
| `MAX_PAGES_PER_COMPANY` | `6` | Pages fetched per scrape run (controls token cost) |
| `RAW_SIGNAL_RETENTION_DAYS` | `1095` | How long raw HTML is kept (3 years) |
| `SCRAPE_PAGE_SUFFIXES` | 5 paths | URL suffixes tried per company (`/about`, `/team`, etc.) |

**Planned config hooks** (placeholders, not yet implemented):
- `SLACK_WEBHOOK_URL` — push digest notifications to Slack
- `SUPABASE_URL` / `SUPABASE_KEY` — swap SQLite → hosted Postgres

---

## Data Model

| Table | Purpose |
|-------|---------|
| `companies` | Current snapshot of each tracked company |
| `events` | Append-only history (funding rounds, acquisitions, leadership changes) |
| `company_relations` | Investors, founders, customers, partners (with valid\_from / valid\_to) |
| `conflicts` | Field values that couldn't be auto-resolved → human review queue |
| `candidate_companies` | Newly discovered companies → human approval queue |
| `raw_signals` | Every raw HTML/text fetched, with timestamps — provenance archive |
| `digests` | Weekly and on-demand CEO-style markdown reports |

---

## Adding New Companies

**Option A — manual:**
Edit `core/seed.py` → add an entry to `COMPANIES` → `python pipeline.py seed`

**Option B — via dashboard:**
Go to **Review → Candidates** tab → Approve any candidate surfaced by the `scan` stage.

**Option C — probe then approve:**
```bash
python pipeline.py probe --company "NewCo" --website https://newco.io
python review_server.py   # approve staged fields in the Review tab
```

---

## Raw Signal Provenance

Every page fetched is archived in `raw_signals`. Trace any field back to its source:

```sql
SELECT source_url, source_type, fetched_at, raw_content
FROM raw_signals
WHERE related_company_ids LIKE '%<company_id>%'
ORDER BY fetched_at DESC;
```
