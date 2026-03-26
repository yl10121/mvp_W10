-- ================================================================
-- MODULE 1: XHS Trend Object Builder
-- Schema: raw scraped posts, processed trend objects, run logs
-- ================================================================

-- Raw + anonymized XHS posts from the live scraper
CREATE TABLE IF NOT EXISTS module1_xhs_posts (
    id                      BIGSERIAL PRIMARY KEY,
    run_id                  TEXT        NOT NULL,
    post_id                 TEXT        NOT NULL,
    keyword                 TEXT,
    category                TEXT,
    date                    TEXT,
    title                   TEXT,                        -- raw, unchanged
    caption                 TEXT,                        -- raw, unchanged
    hashtags                JSONB       DEFAULT '[]',    -- raw, unchanged
    likes                   INTEGER     DEFAULT 0,
    comment_count           INTEGER     DEFAULT 0,       -- count shown on post
    saves                   INTEGER     DEFAULT 0,
    creator                 TEXT,                        -- anonymized SHA-256 hash
    post_link               TEXT,
    cover_url               TEXT,
    all_image_urls          JSONB       DEFAULT '[]',
    is_video                BOOLEAN     DEFAULT FALSE,
    video_url               TEXT,
    image_caption           TEXT,                        -- AI-generated description
    comments_scraped        JSONB       DEFAULT '[]',    -- [{commenter_id, text, likes, replies:[]}]
    comments_count_scraped  INTEGER     DEFAULT 0,
    scraped_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_m1_posts_run    ON module1_xhs_posts (run_id);
CREATE INDEX IF NOT EXISTS idx_m1_posts_kw     ON module1_xhs_posts (keyword);
CREATE INDEX IF NOT EXISTS idx_m1_posts_cat    ON module1_xhs_posts (category);


-- Trend objects produced by the trend builder
CREATE TABLE IF NOT EXISTS module1_trend_objects (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT        NOT NULL,
    trend_id        TEXT        NOT NULL,           -- "t01", "t02", …
    label           TEXT,
    category        TEXT,
    summary         TEXT,
    ai_reasoning    TEXT,
    confidence      TEXT,                           -- "high" / "medium" / "low"
    labeling_source TEXT,                           -- "heuristic" / "llm"
    evidence        JSONB       DEFAULT '{}',       -- {post_ids, snippets, posts[]}
    metrics         JSONB       DEFAULT '{}',       -- engagement + keyword stats
    visual_assets   JSONB       DEFAULT '{}',       -- image URLs + AI captions
    comment_signals JSONB       DEFAULT '{}',       -- anonymized comments + replies
    generated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_m1_trend_run_id
    ON module1_trend_objects (run_id, trend_id);
CREATE INDEX IF NOT EXISTS idx_m1_trend_label     ON module1_trend_objects (label);
CREATE INDEX IF NOT EXISTS idx_m1_trend_conf      ON module1_trend_objects (confidence);


-- Run-level metadata (one row per pipeline execution)
CREATE TABLE IF NOT EXISTS module1_run_logs (
    id                  BIGSERIAL PRIMARY KEY,
    run_id              TEXT        UNIQUE NOT NULL,
    brand               TEXT,
    category            TEXT,
    time_window         JSONB       DEFAULT '{}',
    records_loaded      INTEGER     DEFAULT 0,
    records_retrieved   INTEGER     DEFAULT 0,
    trend_count         INTEGER     DEFAULT 0,
    llm_enabled         BOOLEAN     DEFAULT FALSE,
    llm_model           TEXT,
    llm_errors          JSONB       DEFAULT '[]',
    keywords_scraped    JSONB       DEFAULT '[]',
    generated_at        TIMESTAMPTZ DEFAULT NOW()
);
