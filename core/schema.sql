-- Competitor Intelligence DB — SQLite schema
-- Run once: python -c "from db import Database; Database().init_schema()"

CREATE TABLE IF NOT EXISTS companies (
    id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    website TEXT,
    linkedin_url TEXT,
    hq_city TEXT,
    hq_country TEXT,
    founded_year INTEGER,
    target_customer TEXT,
    core_product TEXT,
    pricing_model TEXT,
    stage_focus TEXT,              -- greenfield / brownfield / resource_def / production
    latest_round_type TEXT,        -- seed / series_a / series_b / etc
    latest_round_amount_usd REAL,
    latest_round_date DATE,
    business_model_summary TEXT,
    -- Full-text fields from source CSV (displayed directly in dashboard)
    technical TEXT,           -- ML/AI architecture description
    stage_description TEXT,   -- mining stage full description
    latest_round_text TEXT,   -- Latest Round (e.g. "Series B · $44M · Jul 2025")
    funding_trajectory TEXT,  -- full funding history narrative
    investors_text TEXT,      -- investors as plain text
    valuation TEXT,           -- valuation info as plain text

    status TEXT DEFAULT 'active',  -- active / acquired / pivoted / dead / stealth
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confidence_score REAL DEFAULT 1.0,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(canonical_name);
CREATE INDEX IF NOT EXISTS idx_companies_website ON companies(website);
CREATE INDEX IF NOT EXISTS idx_companies_status ON companies(status);


CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id),
    event_type TEXT NOT NULL,
    -- funding_round / acquisition / leadership_change / product_launch /
    -- partnership / customer_win / customer_loss / pivot / rebrand /
    -- hiring_signal / tech_disclosure
    event_date DATE NOT NULL,
    payload TEXT NOT NULL,         -- JSON
    fingerprint TEXT UNIQUE NOT NULL,
    source_url TEXT,
    source_tier INTEGER DEFAULT 3, -- 1=highest, 4=lowest
    cross_references TEXT,         -- JSON array of {url, tier}
    extracted_by TEXT,
    confidence REAL DEFAULT 0.5,
    raw_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_company ON events(company_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_date ON events(event_date);
CREATE INDEX IF NOT EXISTS idx_events_fp ON events(fingerprint);


CREATE TABLE IF NOT EXISTS company_relations (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id),
    related_entity_name TEXT NOT NULL,
    related_entity_type TEXT NOT NULL, -- investor / customer / partner / acquirer / advisor / founder
    relation_subtype TEXT,             -- lead / follow / strategic / pilot / paying / etc
    partner_name TEXT,                 -- individual contact (e.g. partner at VC)
    board_seat BOOLEAN DEFAULT 0,
    valid_from DATE,
    valid_to DATE,                     -- NULL = still active
    source_url TEXT,
    confidence REAL DEFAULT 0.5,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_relations_company ON company_relations(company_id);
CREATE INDEX IF NOT EXISTS idx_relations_entity ON company_relations(related_entity_name);
CREATE INDEX IF NOT EXISTS idx_relations_type ON company_relations(related_entity_type);


CREATE TABLE IF NOT EXISTS conflicts (
    id TEXT PRIMARY KEY,
    company_id TEXT REFERENCES companies(id),
    field_name TEXT NOT NULL,
    existing_value TEXT,
    new_value TEXT,
    existing_source TEXT,
    new_source TEXT,
    existing_source_tier INTEGER,
    new_source_tier INTEGER,
    reason TEXT,
    status TEXT DEFAULT 'pending',    -- pending / resolved / dismissed
    resolution TEXT,                  -- accept_new / keep_existing / merge / other
    resolved_value TEXT,
    resolved_at TIMESTAMP,
    resolved_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conflicts_status ON conflicts(status);
CREATE INDEX IF NOT EXISTS idx_conflicts_company ON conflicts(company_id);


CREATE TABLE IF NOT EXISTS candidate_companies (
    id TEXT PRIMARY KEY,
    discovered_name TEXT NOT NULL,
    discovered_url TEXT,
    discovery_source TEXT NOT NULL,
    discovery_reason TEXT,
    initial_evidence TEXT,            -- JSON
    status TEXT DEFAULT 'pending',    -- pending / approved / rejected / duplicate
    rejection_reason TEXT,
    merged_into_company_id TEXT,
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidate_companies(status);


CREATE TABLE IF NOT EXISTS raw_signals (
    id TEXT PRIMARY KEY,
    source_url TEXT NOT NULL,
    source_type TEXT,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    raw_content TEXT,
    extracted_events TEXT,            -- JSON array of event IDs
    related_company_ids TEXT          -- JSON array
);

CREATE INDEX IF NOT EXISTS idx_signals_url ON raw_signals(source_url);
CREATE INDEX IF NOT EXISTS idx_signals_fetched ON raw_signals(fetched_at);


CREATE TABLE IF NOT EXISTS digests (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    digest_type TEXT DEFAULT 'weekly',  -- 'weekly' / 'on_demand'
    company_ids TEXT,                   -- JSON array, NULL = all companies
    content TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_digests_created ON digests(created_at);
