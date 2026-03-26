-- ================================================================
-- MODULE 4: Client Memory Structurer
-- Schema: voice notes → structured client memory objects
-- ================================================================

-- Structured client memory objects extracted from voice memos
CREATE TABLE IF NOT EXISTS module4_client_memories (
    id                  BIGSERIAL PRIMARY KEY,
    run_id              TEXT        NOT NULL,
    raw_voice_note      TEXT,                       -- original input text, unchanged
    summary             TEXT,                       -- 2-4 sentence summary
    life_event          JSONB       DEFAULT '{}',   -- {value, confidence, evidence}
    timeline            JSONB       DEFAULT '{}',
    aesthetic_preference JSONB      DEFAULT '{}',
    size_height         JSONB       DEFAULT '{}',
    budget              JSONB       DEFAULT '{}',
    mood                JSONB       DEFAULT '{}',
    trend_signals       JSONB       DEFAULT '{}',
    next_step_intent    JSONB       DEFAULT '{}',
    model_used          TEXT,
    confidence_summary  JSONB       DEFAULT '{}',   -- {High: N, Medium: N, Low: N}
    missing_fields_count INTEGER    DEFAULT 0,
    generated_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_m4_memories_run      ON module4_client_memories (run_id);
CREATE INDEX IF NOT EXISTS idx_m4_memories_budget   ON module4_client_memories
    ((budget->>'value'));
CREATE INDEX IF NOT EXISTS idx_m4_memories_event    ON module4_client_memories
    ((life_event->>'value'));


-- Reviewer feedback on memory extractions
CREATE TABLE IF NOT EXISTS module4_memory_feedback (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT        NOT NULL,
    memory_id       BIGINT      REFERENCES module4_client_memories(id),
    reviewer        TEXT,
    correctness     INTEGER,                    -- 1-5
    missing_info    TEXT,
    duplicates_noise TEXT,
    usefulness      INTEGER,                    -- 1-5 for follow-up readiness
    submitted_at    TIMESTAMPTZ DEFAULT NOW()
);


-- Run-level metadata
CREATE TABLE IF NOT EXISTS module4_run_logs (
    id                      BIGSERIAL PRIMARY KEY,
    run_id                  TEXT        UNIQUE NOT NULL,
    model_used              TEXT,
    records_processed       INTEGER     DEFAULT 0,
    missing_fields_avg      NUMERIC,
    generated_at            TIMESTAMPTZ DEFAULT NOW()
);
