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

### Table: `module1_xhs_posts` (one row per scraped post)

| Column                 | Type        | Required | Notes                                            |
|------------------------|-------------|----------|--------------------------------------------------|
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
| image_caption          | text        | no       | AI-generated description of the cover image       |
| comments_scraped       | jsonb       | no       | Array of {commenter_id, text, likes, replies:[]}  |
| comments_count_scraped | integer     | no       | len(comments_scraped)                             |

### Table: `module1_trend_objects` (one row per trend)

| Column           | Type        | Required | Notes                                                      |
|------------------|-------------|----------|------------------------------------------------------------|
| run_id           | text        | yes      | Links trend back to its pipeline run                        |
| trend_id         | text        | yes      | Sequential ID within the run ("t01", "t02", ...)            |
| label            | text        | no       | Short human-readable trend name                             |
| category         | text        | no       | Copied from run config                                      |
| summary          | text        | no       | One-sentence description of what the trend represents       |
| ai_reasoning     | text        | no       | LLM explanation of why posts were clustered and confidence chosen |
| confidence       | text        | no       | "high", "medium", or "low"                                  |
| labeling_source  | text        | no       | "heuristic" or "llm"                                        |
| evidence         | jsonb       | no       | {post_ids:[], snippets:[], posts:[]} -- grounding artifacts |
| metrics          | jsonb       | no       | {post_count, total_engagement, ...} computed from data only |
| visual_assets    | jsonb       | no       | Image URLs and AI captions linked to the trend              |
| comment_signals  | jsonb       | no       | Anonymized comments and replies that support the trend      |

#### Evidence fields (what we store to prove grounding)

- `evidence.post_ids` -- list of post_id values that belong to this cluster.
- `evidence.snippets` -- short excerpts (titles/captions) from those posts.
- `evidence.posts` -- full post objects with engagement numbers, dates, and media URLs.
- `ai_reasoning` -- free-text explanation produced by the LLM justifying the cluster and its confidence level.
- `labeling_source` -- whether the label/summary came from rule-based heuristics or the LLM.

#### Confidence field

`confidence` is one of three values:
- **high** -- evidence is coherent, sufficient, and posts clearly share a distinct theme.
- **medium** -- signal is present but partially mixed or cluster size is borderline.
- **low** -- evidence is sparse, weak, or ambiguous.

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
