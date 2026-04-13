-- Module 2: Trend Relevance & Materiality Filter
-- Stores the LLM-evaluated shortlist of top trends passed to Module 3.

CREATE TABLE IF NOT EXISTS module2_trend_shortlist (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT NOT NULL,
    module1_run_id  TEXT,
    brand           TEXT,
    trend_id        TEXT,
    rank            INTEGER,
    label           TEXT,
    category        TEXT,
    composite_score NUMERIC(5,2),
    score_freshness     NUMERIC(4,1),
    score_brand_fit     NUMERIC(4,1),
    score_category_fit  NUMERIC(4,1),
    score_materiality   NUMERIC(4,1),
    score_actionability NUMERIC(4,1),
    confidence          TEXT,
    why_selected        TEXT,
    evidence_references JSONB DEFAULT '[]',
    metric_signal       JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_m2_shortlist_run ON module2_trend_shortlist(run_id);
CREATE INDEX IF NOT EXISTS idx_m2_shortlist_trend ON module2_trend_shortlist(trend_id);

-- Align with production Supabase (extended M2 schema). Safe on DBs that already have these columns.
ALTER TABLE module2_trend_shortlist ADD COLUMN IF NOT EXISTS location TEXT;
ALTER TABLE module2_trend_shortlist ADD COLUMN IF NOT EXISTS data_type TEXT;
ALTER TABLE module2_trend_shortlist ADD COLUMN IF NOT EXISTS subcategory TEXT;
ALTER TABLE module2_trend_shortlist ADD COLUMN IF NOT EXISTS client_persona_match_name TEXT;
ALTER TABLE module2_trend_shortlist ADD COLUMN IF NOT EXISTS hero_product TEXT;
ALTER TABLE module2_trend_shortlist ADD COLUMN IF NOT EXISTS score_ca_conversational_utility NUMERIC(4,1);
ALTER TABLE module2_trend_shortlist ADD COLUMN IF NOT EXISTS score_language_specificity NUMERIC(4,1);
ALTER TABLE module2_trend_shortlist ADD COLUMN IF NOT EXISTS score_client_persona_match NUMERIC(4,1);
ALTER TABLE module2_trend_shortlist ADD COLUMN IF NOT EXISTS score_novelty NUMERIC(4,1);
ALTER TABLE module2_trend_shortlist ADD COLUMN IF NOT EXISTS score_trend_velocity NUMERIC(4,1);
ALTER TABLE module2_trend_shortlist ADD COLUMN IF NOT EXISTS score_cross_run_persistence NUMERIC(4,1);
ALTER TABLE module2_trend_shortlist ADD COLUMN IF NOT EXISTS engagement_recency_pct NUMERIC(5,2);
ALTER TABLE module2_trend_shortlist ADD COLUMN IF NOT EXISTS low_signal_warning BOOLEAN;
ALTER TABLE module2_trend_shortlist ADD COLUMN IF NOT EXISTS no_date_signal BOOLEAN;
ALTER TABLE module2_trend_shortlist ADD COLUMN IF NOT EXISTS disqualifying_reason TEXT;
ALTER TABLE module2_trend_shortlist ADD COLUMN IF NOT EXISTS hero_product_source TEXT;


CREATE TABLE IF NOT EXISTS module2_run_logs (
    id                   BIGSERIAL PRIMARY KEY,
    run_id               TEXT UNIQUE NOT NULL,
    module1_run_id       TEXT,
    total_input          INTEGER,
    prefilter_rejected   INTEGER,
    passed_to_llm        INTEGER,
    shortlisted          INTEGER,
    noise_reduction_pct  NUMERIC(5,1),
    generated_at         TIMESTAMPTZ,
    created_at           TIMESTAMPTZ DEFAULT NOW()
);
