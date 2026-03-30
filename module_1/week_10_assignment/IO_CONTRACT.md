# Module 1 -- I/O Contract

## Inputs

### Config file (`data/run_config.json`)

| Field               | Type    | Required | Notes                                      |
|---------------------|---------|----------|--------------------------------------------|
| brand               | string  | yes      | e.g. "Celine"                              |
| category            | string  | yes      | e.g. "luxury_fashion"                       |
| time_window.start_date | string | yes   | ISO date, inclusive                          |
| time_window.end_date   | string | yes   | ISO date, inclusive                          |
| max_posts           | integer | yes      | Upper bound on posts retrieved              |
| top_k_trends        | integer | yes      | Max trend objects to produce                |
| min_posts_per_trend | integer | yes      | Cluster must have >= N posts to emit        |
| llm.enabled         | boolean | no       | Default false; enables LLM labeling pass    |
| llm.model           | string  | no       | Model ID used when llm.enabled is true      |
| prompt              | string  | no       | System prompt fed to the trend builder LLM  |

### Assumptions

- Posts are scraped from Xiaohongshu (XHS) via Playwright; the scraper populates `data/xhs_posts.json`.
- Creator names are SHA-256-hashed at scrape time (`anonymize_creator`); no PII reaches the database.
- Comment text is stored verbatim but commenter identities are anonymized the same way.
- A single run processes one brand + one category + one time window.

---

## Outputs

### Current Supabase state

As of the latest pipeline run, the database contains **60 posts** in `module1_xhs_posts` and **8 trend objects** in `module1_trend_objects`.

---

### Table: `module1_xhs_posts` (one row per scraped post)

| Column                 | Type        | Required | Notes                                            |
|------------------------|-------------|----------|--------------------------------------------------|
| id                     | integer     | yes      | Auto-generated primary key                        |
| run_id                 | text        | yes      | Links post back to its pipeline run               |
| post_id                | text        | yes      | Synthetic ID assigned by scraper (e.g. "live_0001") |
| keyword                | text        | no       | Search keyword that surfaced this post            |
| category               | text        | no       | Copied from run config                            |
| date                   | text        | no       | Post publish date as scraped                      |
| title                  | text        | no       | Raw post title, unchanged                         |
| caption                | text        | no       | Raw post body/caption, unchanged                  |
| hashtags               | jsonb       | no       | Array of hashtag strings                          |
| likes                  | integer     | no       | Defaults to 0                                     |
| comment_count          | integer     | no       | Comment count shown on the post listing           |
| saves                  | integer     | no       | Defaults to 0                                     |
| creator                | text        | no       | Anonymized SHA-256 hash of the creator name       |
| post_link              | text        | no       | Original XHS URL                                  |
| cover_url              | text        | no       | URL of the post cover image                       |
| all_image_urls         | jsonb       | no       | Array of all image URLs attached to the post      |
| is_video               | boolean     | no       | Whether the post is a video post                  |
| video_url              | text        | no       | URL of the video if the post is a video           |
| image_caption          | text        | no       | AI-generated description of the cover image       |
| comments_scraped       | jsonb       | no       | Array of {commenter_id, text, likes, replies:[]}  |
| comments_count_scraped | integer     | no       | len(comments_scraped)                             |
| scraped_at             | timestamptz | no       | Timestamp when the post was scraped               |

### Table: `module1_trend_objects` (one row per trend)

Trend objects are produced via **LLM-first clustering**. The LLM reads the full set of scraped posts and groups them into coherent trends, producing labels, summaries, confidence levels, and reasoning in a single pass. There is no heuristic pre-clustering step; the LLM is the primary clustering engine.

| Column           | Type        | Required | Notes                                                      |
|------------------|-------------|----------|------------------------------------------------------------|
| id               | integer     | yes      | Auto-generated primary key                                  |
| run_id           | text        | yes      | Links trend back to its pipeline run                        |
| trend_id         | text        | yes      | Sequential ID within the run ("t01", "t02", ...)            |
| label            | text        | no       | Short human-readable trend name                             |
| category         | text        | no       | Copied from run config                                      |
| summary          | text        | no       | One-sentence description of what the trend represents       |
| ai_reasoning     | text        | no       | LLM explanation of why posts were clustered and confidence chosen |
| confidence       | text        | no       | "high", "medium", or "low" (see below)                      |
| labeling_source  | text        | no       | "llm" (LLM-first clustering is the default pipeline)        |
| evidence         | jsonb       | no       | {post_ids:[], snippets:[], posts:[]} -- grounding artifacts |
| metrics          | jsonb       | no       | {post_count, total_engagement, ...} computed from data only |
| visual_assets    | jsonb       | no       | Image URLs and AI captions linked to the trend              |
| comment_signals  | jsonb       | no       | Anonymized comments and replies that support the trend      |
| generated_at     | timestamptz | no       | Timestamp when the trend object was generated               |

#### Confidence field

`confidence` is one of three values assigned by the LLM during clustering:

- **high** -- Coherent evidence across multiple posts that clearly share a distinct theme. Engagement signals and content align.
- **medium** -- Signal is present but mixed. The theme exists in the data but posts may partially overlap with other clusters, or supporting evidence is uneven.
- **low** -- Evidence is sparse or ambiguous. Few posts, weak engagement, or the thematic link between posts is tenuous.

#### Evidence fields (what we store to prove grounding)

- `evidence.post_ids` -- List of post_id values that belong to this cluster.
- `evidence.snippets` -- Short excerpts (titles/captions) from those posts.
- `evidence.posts` -- Top 5 posts by engagement, including full post objects with engagement numbers, dates, and media URLs.
- `ai_reasoning` -- Free-text explanation produced by the LLM justifying the cluster and its confidence level.
- `labeling_source` -- Indicates the source of the label and summary. With LLM-first clustering, this is "llm".

### Table: `module1_run_logs` (one row per pipeline execution)

| Column            | Type        | Required | Notes                                       |
|-------------------|-------------|----------|---------------------------------------------|
| run_id            | text        | yes      | Unique, e.g. "run_0013"                      |
| brand             | text        | no       | From run config                               |
| category          | text        | no       | From run config                               |
| time_window       | jsonb       | no       | {start_date, end_date}                        |
| records_loaded    | integer     | no       | Total posts loaded from source file           |
| records_retrieved | integer     | no       | Posts remaining after time-window filter       |
| trend_count       | integer     | no       | Number of trend objects emitted               |
| llm_enabled       | boolean     | no       | Whether the LLM labeling pass was active      |
| llm_model         | text        | no       | Model ID used (empty when llm_enabled=false)  |
| llm_errors        | jsonb       | no       | Array of error strings from LLM calls         |
| keywords_scraped  | jsonb       | no       | Array of search keywords used in the run      |
