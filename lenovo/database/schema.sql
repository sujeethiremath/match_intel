-- ── 1. MATCHES ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS matches (
    id SERIAL PRIMARY KEY,
    sport VARCHAR(10) NOT NULL,
    gender VARCHAR(6) NOT NULL,
    competition TEXT NOT NULL,
    team_a TEXT NOT NULL,
    team_b TEXT NOT NULL,
    venue TEXT,
    match_date DATE NOT NULL,
    match_time_utc TIMESTAMPTZ,
    match_format VARCHAR(30),
    match_status VARCHAR(12) DEFAULT 'PREVIEW',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(team_a, team_b, match_date, sport, gender)
);

-- ── 2. RAW SCRAPED DATA ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS raw_scraped_data (
    id SERIAL PRIMARY KEY,
    match_id INT REFERENCES matches(id) ON DELETE CASCADE,
    source_name TEXT NOT NULL,
    source_url TEXT,
    raw_content JSONB,
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    success BOOLEAN DEFAULT TRUE,
    error_msg TEXT
);

-- ── 3. PROCESSED MATCH DATA ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS processed_match_data (
    id SERIAL PRIMARY KEY,
    match_id INT REFERENCES matches(id) ON DELETE CASCADE UNIQUE,
    recent_form_a JSONB,
    recent_form_b JSONB,
    h2h_record JSONB,
    squad_a JSONB,
    squad_b JSONB,
    injury_news JSONB,
    venue_stats JSONB,
    weather JSONB,
    pitch_report TEXT,
    processed_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── 4. AI ANALYSIS ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_analysis (
    id SERIAL PRIMARY KEY,
    match_id INT REFERENCES matches(id) ON DELETE CASCADE UNIQUE,
    model_used TEXT,
    strengths_a JSONB,
    strengths_b JSONB,
    weaknesses_a JSONB,
    weaknesses_b JSONB,
    key_decider_factors JSONB,
    h2h_synthesis TEXT,
    match_context TEXT,
    predicted_winner TEXT,
    pick_reasoning TEXT,
    analysis_complete BOOLEAN DEFAULT FALSE,
    analyzed_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── 5. PLAYER STATS CACHE (TTL 14 Days) ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS player_stats_cache (
    player_id TEXT PRIMARY KEY,
    player_name TEXT,
    career_stats JSONB,
    last_updated TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_player_cache_updated ON player_stats_cache(last_updated);

-- ── 6. PIPELINE & EMAIL LOGS ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id SERIAL PRIMARY KEY,
    run_date DATE NOT NULL,
    stage_name TEXT NOT NULL,
    status VARCHAR(10) DEFAULT 'RUNNING',
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    matches_processed INT DEFAULT 0,
    notes TEXT,
    error_log TEXT
);

CREATE TABLE IF NOT EXISTS email_log (
    id SERIAL PRIMARY KEY,
    run_date DATE NOT NULL,
    sent_at TIMESTAMPTZ,
    status VARCHAR(10) DEFAULT 'PENDING',
    recipient TEXT,
    matches_included INT DEFAULT 0,
    error_message TEXT,
    html_snapshot TEXT
);