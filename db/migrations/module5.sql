-- ================================================================
-- MODULE 5: Outreach Angle Agent
-- Schema: outreach suggestions, WeChat drafts, run logs
-- ================================================================

-- Outreach suggestions generated per client
CREATE TABLE IF NOT EXISTS module5_outreach_suggestions (
    id                  BIGSERIAL PRIMARY KEY,
    run_id              TEXT        NOT NULL,
    client_id           TEXT,                       -- anonymized client reference
    outreach_angle      TEXT,                       -- recommended approach angle
    wechat_draft        TEXT,                       -- generated WeChat message draft
    reasoning           TEXT,                       -- why this angle was chosen
    trend_signals_used  JSONB       DEFAULT '[]',   -- which trend signals informed this
    client_memory_ref   JSONB       DEFAULT '{}',   -- summary of client memory used
    confidence          TEXT,                       -- "high" / "medium" / "low"
    model_used          TEXT,
    generated_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_m5_outreach_run     ON module5_outreach_suggestions (run_id);
CREATE INDEX IF NOT EXISTS idx_m5_outreach_client  ON module5_outreach_suggestions (client_id);
CREATE INDEX IF NOT EXISTS idx_m5_outreach_conf    ON module5_outreach_suggestions (confidence);


-- Human review of generated outreach drafts
CREATE TABLE IF NOT EXISTS module5_outreach_feedback (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT        NOT NULL,
    suggestion_id   BIGINT      REFERENCES module5_outreach_suggestions(id),
    reviewer        TEXT,
    quality_score   INTEGER,                    -- 1-5
    sent_to_client  BOOLEAN     DEFAULT FALSE,  -- did the SA actually send it?
    outcome         TEXT,                       -- what happened after sending
    notes           TEXT,
    submitted_at    TIMESTAMPTZ DEFAULT NOW()
);


-- Raw run log from each agent execution
CREATE TABLE IF NOT EXISTS module5_run_logs (
    id                  BIGSERIAL PRIMARY KEY,
    run_id              TEXT        UNIQUE NOT NULL,
    client_id           TEXT,
    model_used          TEXT,
    prompt_version      TEXT,
    suggestions_count   INTEGER     DEFAULT 0,
    run_log_raw         JSONB       DEFAULT '{}',   -- full run_log.json payload
    generated_at        TIMESTAMPTZ DEFAULT NOW()
);
