-- Phase 2: Local opportunity store and run history

CREATE TABLE IF NOT EXISTS opportunities (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    content_hash TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    prior_content_hash TEXT,
    data TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    UNIQUE(source, source_id)
);

CREATE INDEX IF NOT EXISTS idx_opportunities_source ON opportunities(source);
CREATE INDEX IF NOT EXISTS idx_opportunities_status ON opportunities(status);
CREATE INDEX IF NOT EXISTS idx_opportunities_last_seen ON opportunities(last_seen_at);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    items_fetched INTEGER NOT NULL DEFAULT 0,
    items_new INTEGER NOT NULL DEFAULT 0,
    items_amended INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_runs_source ON runs(source);
CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at);

-- Phase 4: Example opportunities for AI relevance scoring
CREATE TABLE IF NOT EXISTS examples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL,
    url TEXT NOT NULL,
    label TEXT NOT NULL CHECK (label IN ('good', 'bad')),
    title TEXT,
    summary TEXT,
    raw_text TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_examples_profile ON examples(profile_id);
CREATE INDEX IF NOT EXISTS idx_examples_label ON examples(label);
