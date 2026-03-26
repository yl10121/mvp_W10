-- ================================================================
-- MODULE 3: Trend Brief Agent
-- Schema: generated trend briefs + run logs
-- ================================================================

-- Full trend brief outputs (one row per brand/city run)
CREATE TABLE IF NOT EXISTS module3_trend_briefs (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT        NOT NULL,
    brand           TEXT,
    city            TEXT,
    output_markdown TEXT,                       -- full brief as markdown
    output_html     TEXT,                       -- rendered HTML version
    trend_cards     JSONB       DEFAULT '[]',   -- parsed trend card objects
    source_file     TEXT,                       -- path to input trend_shortlist.json
    model_used      TEXT,
    generated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_m3_briefs_run    ON module3_trend_briefs (run_id);
CREATE INDEX IF NOT EXISTS idx_m3_briefs_brand  ON module3_trend_briefs (brand);
CREATE INDEX IF NOT EXISTS idx_m3_briefs_city   ON module3_trend_briefs (city);


-- Feedback entries logged for each brief
CREATE TABLE IF NOT EXISTS module3_brief_feedback (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT        NOT NULL,
    brief_id        BIGINT      REFERENCES module3_trend_briefs(id),
    reviewer        TEXT,
    quality_score   INTEGER,                    -- 1-5
    missing_info    TEXT,
    duplicates_noise TEXT,
    notes           TEXT,
    submitted_at    TIMESTAMPTZ DEFAULT NOW()
);


-- Run-level metadata
CREATE TABLE IF NOT EXISTS module3_run_logs (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT        UNIQUE NOT NULL,
    brand           TEXT,
    city            TEXT,
    model_used      TEXT,
    brief_count     INTEGER     DEFAULT 0,
    error           TEXT,
    generated_at    TIMESTAMPTZ DEFAULT NOW()
);
