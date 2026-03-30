# Module 1 -- XHS Trend Object Builder

## Week 10 Assignment Deliverables

| Part | Deliverable | File | Status |
|------|------------|------|--------|
| A1 | Batch dataset (197 real XHS posts) | [data/xhs_posts.json](data/xhs_posts.json) | Done |
| A2 | Data Card | [DATA_CARD.md](DATA_CARD.md) | Done |
| B1 | I/O Contract | [IO_CONTRACT.md](IO_CONTRACT.md) | Done |
| B2 | Supabase populated (60 posts + 8 trends) | Supabase `module1_xhs_posts`, `module1_trend_objects` | Done |
| C1 | 3 quality checks | [eval_harness.py](eval_harness.py) | Done |
| C2 | Evaluation report | [outputs/EVAL_REPORT.md](outputs/EVAL_REPORT.md) | Done |
| D1-D3 | Testing plan + demo script | [TEST_PLAN.md](TEST_PLAN.md) | Done |
| E | 7-line demo script | Included in [TEST_PLAN.md](TEST_PLAN.md) | Done |

---

## What Module 1 Does

Module 1 scrapes Xiaohongshu (XHS) posts for a given brand, then identifies **XHS content trends** -- recurring patterns in what users are posting, discussing, and debating on the platform.

**Input:** XHS keyword searches (e.g. "Celine", "Celine包包", "静奢风穿搭")
**Output:** Structured trend objects with evidence, metrics, and confidence scores

### Pipeline

```
xhs_scraper_pw.py          Playwright scraper -- searches XHS, extracts post details
        |
        v
data/xhs_posts.json        197 real posts with titles, captions, hashtags, engagement, images
        |
        v
xhs_trend_builder.py       LLM-first clustering -- reads all posts, identifies content trends
        |
        v
outputs/trend_objects.json  8 trend objects with evidence, metrics, confidence
        |
        v
Supabase                   module1_xhs_posts (60 rows), module1_trend_objects (8 rows)
        |
        v
eval_harness.py            3 quality checks, generates EVAL_REPORT.md
```

---

## Latest Trend Objects (run_0022, real XHS data)

| Trend | Posts | Engagement | Confidence |
|-------|-------|-----------|------------|
| Old Celine vs New Celine Nostalgia Debate | 12 | 48,345 | high |
| Soft 16 Bag Functional Reviews and Styling | 8 | 25,695 | high |
| Celine Men's Fashion and Male Accessory Focus | 12 | 21,998 | medium |
| Celebrity Outfit Decoding and Influence | 10 | 13,786 | medium |
| Celine 26 Spring/Summer Fashion Show Content | 14 | 5,656 | medium |
| Celine Box Bag Relevance and Popularity Debate | 10 | 3,224 | high |
| French Old Money and Elegant Aesthetic Styling | 7 | 1,381 | medium |
| Celine Bag Unboxing and Purchase Experience | 10 | 917 | high |

---

## Evaluation Results (run_0022)

| Check | Result | Details |
|-------|--------|---------|
| Duplication Rate | FAIL (3/8) | 5 post_ids shared across trend clusters |
| Evidence Sufficiency | PASS (8/8) | All trends have sufficient posts, snippets, engagement |
| Label Clarity | FAIL (7/8) | 1 label exceeds 8-word limit |

**Planned fix for Week 11:** Add a deduplication pass after LLM clustering to remove shared post_ids -- assign each post to its highest-engagement trend only.

---

## How to Run

### Prerequisites

```bash
cd module_1
python3 -m venv .venv
.venv/bin/pip install -r ../requirements.txt
.venv/bin/pip install playwright
.venv/bin/python3 -m playwright install chromium
```

### 1. Scrape XHS (requires Chrome + QR login)

```bash
.venv/bin/python3 run_celine_scrape.py
```

- Opens Chrome, scan QR code with your XHS app (once -- cookies saved)
- Scrapes 25 keywords with 5 parallel tabs per keyword
- Saves to disk after every keyword (safe to Ctrl+C anytime)
- Output: `data/xhs_posts.json`

### 2. Build Trend Objects

```bash
OPENROUTER_API_KEY=<key> ../.venv/bin/python3 xhs_trend_builder.py
```

- Reads all posts from `data/xhs_posts.json`
- LLM-first clustering: sends all post titles to the LLM, which identifies XHS content trends and assigns posts to each
- Falls back to heuristic token-based clustering if LLM is unavailable
- Output: `outputs/runs/run_XXXX_trend_objects.json`
- Syncs to Supabase (`module1_run_logs`, `module1_trend_objects`) if `SUPABASE_PASSWORD` is set

### 3. Run Evaluation

```bash
../.venv/bin/python3 eval_harness.py
```

- Runs 3 quality checks on the latest trend objects
- Checks: duplication rate, evidence sufficiency, label clarity
- Output: `outputs/EVAL_REPORT.md` + `outputs/eval_results.json`

### 4. Full Pipeline (all modules 1-5)

```bash
cd ..
.venv/bin/python3 main.py
```

---

## Data Privacy

- All creator usernames are anonymized via one-way SHA-256 hash
- No real names stored anywhere (not even in raw data)
- Comment text preserved raw (teacher requirement) but commenter IDs hashed
- Anonymization is irreversible

---

## Data Schema

### xhs_posts.json (per record)

```json
{
  "post_id": "live_0001",
  "keyword": "Celine",
  "category": "luxury_fashion",
  "date": "03-21",
  "title": "CELINE早春手袋",
  "caption": "raw post description",
  "hashtags": ["#CELINE", "#手袋"],
  "likes": 3378,
  "comment_count": 0,
  "saves": 1162,
  "creator": "user_683a7c8c",
  "post_link": "https://www.xiaohongshu.com/explore/...",
  "all_image_urls": ["https://..."],
  "cover_url": "https://...",
  "is_video": false,
  "video_url": "",
  "image_caption": "AI-generated image description",
  "comments_scraped": [],
  "comments_count_scraped": 0
}
```

### trend_objects.json (per trend)

```json
{
  "trend_id": "t01",
  "label": "Old Celine vs New Celine Nostalgia Debate",
  "category": "luxury_fashion",
  "summary": "XHS users debating Phoebe Philo era vs Hedi Slimane aesthetic",
  "ai_reasoning": "Posts cluster around old vs new Celine discourse...",
  "confidence": "high",
  "labeling_source": "llm",
  "evidence": {
    "post_ids": ["live_0033", "live_0006", ...],
    "snippets": ["这是真的设计鬼才，他执掌的Celine最有灵魂", ...],
    "posts": [...]
  },
  "metrics": {
    "post_count": 12,
    "total_engagement": 48345,
    "total_likes": 45000,
    "total_comments": 2000,
    "total_saves": 1345
  }
}
```

---

## Key Files

| File | Purpose |
|------|---------|
| `xhs_scraper_pw.py` | Playwright-based XHS scraper (5 parallel tabs) |
| `xhs_trend_builder.py` | Trend object builder with LLM-first clustering |
| `eval_harness.py` | Evaluation harness (3 quality checks) |
| `run_celine_scrape.py` | Quick launcher for Celine keyword scrape |
| `data/xhs_posts.json` | 197 real scraped XHS posts |
| `data/run_config.json` | Scraper/builder configuration |
| `outputs/trend_objects.json` | Latest trend objects (run_0022) |
| `outputs/EVAL_REPORT.md` | Latest evaluation report |
| `DATA_CARD.md` | Part A -- batch data documentation |
| `IO_CONTRACT.md` | Part B -- Supabase I/O schema |
| `TEST_PLAN.md` | Parts D+E -- testing plan + demo script |
