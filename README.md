# Agent Pipeline — Modules 1–5 · Brand: Louis Vuitton

A sequential multi-module AI agent pipeline for LVMH luxury clienteling. Scrapes Xiaohongshu (XHS) trends, filters them for brand relevance, generates CA briefing cards, structures client memory, and produces personalized outreach — persisting everything to Supabase automatically.

**Brand:** Louis Vuitton (configurable via `BRAND` in `.env`)  
**Live repo:** [github.com/m-ny/mvp](https://github.com/m-ny/mvp)

---

## Pipeline Flow

```
Module 1 → Module 2 → Module 3 → Module 4 → Module 5
  XHS        Filter     CA Brief  Client     Outreach
  Scraper    Agent      Agent     Memory     Agent
```

| # | Module | Input | Output |
|---|--------|-------|--------|
| 1 | XHS Trend Builder | Live XHS scrape | `trend_objects.json` |
| 2 | Trend Relevance Filter | M1 trend objects | `output_shortlist.json` → M3 `trend_shortlist.json` |
| 3 | CA Trend Brief | M2 shortlist | Markdown trend cards |
| 4 | Client Memory Structurer | Voice memo / text | Structured client memory |
| 5 | Outreach Angle Agent | Client memory + trends | WeChat draft + outreach angle |

---

## Project Structure

```
Agent/
├── main.py                  ← runs all 5 modules in order (1→2→3→4→5)
├── config.py                ← global API key + model + brand loader
├── supabase_client.py       ← shared Postgres connection factory
├── requirements.txt
├── .env.example             ← copy to .env and fill in secrets
│
├── db/
│   ├── setup.py             ← creates all Supabase tables
│   └── migrations/
│       ├── module1.sql      ← XHS posts + trend objects + run logs
│       ├── module2.sql      ← trend shortlist + run logs
│       ├── module3.sql      ← trend briefs + feedback
│       ├── module4.sql      ← client memory objects
│       └── module5.sql      ← outreach suggestions
│
├── module_1/                ← XHS Trend Object Builder
│   ├── xhs_scraper_live.py  ← live XHS scraper (Chrome + DrissionPage)
│   ├── xhs_trend_builder.py ← clusters posts → trend objects
│   └── supabase_writer.py
│
├── module_2/                ← Trend Relevance & Materiality Filter
│   ├── agent.py             ← main entry point
│   ├── evaluator.py         ← LLM scoring engine (OpenRouter)
│   ├── scorer.py            ← deterministic pre-filter (no LLM)
│   ├── prompts.py           ← Brand-specific evaluation prompts
│   ├── brand_profile.json   ← Brand config, taboos, categories
│   └── supabase_writer.py
│
├── module_3/trend_brief_agent/
│   ├── agent.py             ← generates CA trend brief cards (OpenRouter)
│   ├── trend_shortlist.json ← written here by Module 2
│   └── supabase_writer.py
│
├── module_4/
│   ├── First_Run.py         ← voice memo → structured client memory
│   └── supabase_writer.py
│
└── module_5/
    ├── agent.py             ← outreach angle + WeChat draft
    └── supabase_writer.py
```

---

## Quick Start

### 1. Install dependencies

```bash
pip3 install -r requirements.txt
```

For module 1 live scraping (virtual env recommended on Mac):
```bash
cd module_1
python3 -m venv .venv
.venv/bin/pip install DrissionPage pandas tqdm openpyxl
```

### 2. Configure secrets

```bash
cp .env.example .env
```

Edit `.env`:
```env
# AI — get your key at openrouter.ai
OPENROUTER_API_KEY=your_openrouter_api_key_here
DEFAULT_MODEL=openai/gpt-4o-mini

# Brand (used by all modules)
BRAND=Louis Vuitton

# Supabase — from your project's connection settings
SUPABASE_PASSWORD=your_supabase_db_password_here
SUPABASE_HOST=aws-1-ap-northeast-1.pooler.supabase.com
SUPABASE_PORT=6543
SUPABASE_DB=postgres
SUPABASE_USER=postgres.krfdyudabrlmjixbdcxm
```

### 3. Create Supabase tables (one time)

```bash
python3 db/setup.py
```

Runs all 5 migration files. Safe to re-run — uses `IF NOT EXISTS` everywhere.

To only set up one module:
```bash
python3 db/setup.py --module 2
```

### 4. Run the full pipeline

```bash
python3 main.py
```

Or run individual modules:
```bash
# Module 1 — scrape XHS then build trend objects
cd module_1
.venv/bin/python3 xhs_scraper_live.py --keywords "Louis Vuitton" "LV" "路易威登" --times 3
.venv/bin/python3 xhs_trend_builder.py

# Module 2 — filter + score trends for brand relevance
cd module_2
python3 agent.py

# Module 3 — generate CA trend brief cards
cd module_3/trend_brief_agent
python3 agent.py

# Module 4 — structure client voice memos
cd module_4
python3 First_Run.py

# Module 5 — generate outreach angles
cd module_5
python3 agent.py
```

---

## Module 2 — Trend Relevance & Materiality Filter

Module 2 sits between the raw XHS trend builder and the CA brief generator. It applies a **two-stage qualification pipeline** to eliminate noise and surface only the most brand-relevant trends for the configured brand (`BRAND` in `.env`).

### What it does
1. **Deterministic pre-filter** (no LLM cost): rejects trends that are stale (>21 days old), have too little engagement, wrong category, or contain brand taboo keywords.
2. **LLM evaluation** via OpenRouter: scores each passing trend on 5 dimensions — Freshness, Brand Fit, Category Fit, Materiality, Actionability.
3. **Shortlist** top 5 trends above composite score 6.5 (weighted: brand fit ×0.30, freshness ×0.20, category fit ×0.20, materiality ×0.15, actionability ×0.15).
4. **Writes Module 3 input**: converts shortlist to `trend_shortlist.json` format in `module_3/trend_brief_agent/`.

### Brand profile (Louis Vuitton by default)
Located at `module_2/brand_profile.json`. Edit this to change the brand without touching any code:
- `active_categories`: what product categories to accept (currently `ready-to-wear`, `leather goods`)
- `brand_taboos`: keyword rejection list (streetwear, hypebeast, dupes, etc.)
- `aesthetic`: used by LLM to evaluate brand fit

### Changing the brand
```bash
# In .env
BRAND=Fendi

# Update module_2/brand_profile.json to reflect the new brand
```

---

## Supabase Schema — One Table Group Per Module

Each module owns its own tables. They never share tables across modules.

### Module 1 — XHS Trend Object Builder

| Table | What it stores |
|---|---|
| `module1_xhs_posts` | Every scraped/processed XHS post. Raw titles, captions, hashtags unchanged. Anonymized creator IDs. All image URLs. AI image captions. Full comment + reply text (commenter names hashed). |
| `module1_trend_objects` | Each trend cluster: label, summary, AI reasoning, confidence, evidence posts, engagement metrics, image URLs, and all anonymized comment signals. |
| `module1_run_logs` | One row per pipeline run. Records LLM config, keywords, timing. |

### Module 2 — Trend Relevance Filter

| Table | What it stores |
|---|---|
| `module2_trend_shortlist` | Top 5 shortlisted trends per run with all 5 dimension scores, composite score, confidence, reasoning, and evidence references. |
| `module2_run_logs` | Per-run metadata: how many passed pre-filter, LLM evaluated, shortlisted, noise reduction %. |

### Module 3 — Trend Brief Agent

| Table | What it stores |
|---|---|
| `module3_trend_briefs` | Full trend brief as markdown + HTML. Parsed trend cards as JSONB. Brand + city context. |
| `module3_brief_feedback` | Human reviewer quality scores (1–5), missing info notes. |
| `module3_run_logs` | Per-run metadata. |

### Module 4 — Client Memory Structurer

| Table | What it stores |
|---|---|
| `module4_client_memories` | Extracted client memory object: life event, timeline, aesthetic, budget, mood, trend signals, next-step intent. Each field has value + confidence + evidence. |
| `module4_memory_feedback` | Reviewer correctness + usefulness scores. |
| `module4_run_logs` | Per-run metadata. |

### Module 5 — Outreach Angle Agent

| Table | What it stores |
|---|---|
| `module5_outreach_suggestions` | Outreach angle, WeChat message draft, reasoning, trend signals used, client memory reference. |
| `module5_outreach_feedback` | Was it sent? What was the outcome? |
| `module5_run_logs` | Per-run metadata + full raw run_log.json as JSONB. |

---

## How Supabase sync works

Supabase sync is **automatic and silent** — it runs at the end of each module if `SUPABASE_PASSWORD` is set. If it's not set, the module still runs normally and just skips the DB write.

```
SUPABASE_PASSWORD set → data synced after every run
SUPABASE_PASSWORD not set → module runs fine, no DB writes
```

Check written data: Supabase dashboard → Table Editor.

---

## AI Prompts — use these with Cursor / Claude to extend the pipeline

### Change the brand across all modules

```
Update the pipeline in /Users/mannyhernandez/Documents/GitHub/Agent to target [BRAND_NAME] instead of the current default.
1. Update .env: BRAND=[BRAND_NAME]
2. Update module_2/brand_profile.json: brand_name, aesthetic, clientele, brand_taboos, active_categories
3. Update module_3/trend_brief_agent/agent.py: brand default and system prompt
Make sure all prompts reference the new brand's codes and clientele accurately.
```

### Connect a new module to Supabase

```
I have a Python agent in module_X/agent.py that outputs a dict called `result`.
The project uses supabase_client.py at the root with get_conn(), insert_row(), insert_rows().
SUPABASE_PASSWORD is set in .env.

Create module_X/supabase_writer.py that:
1. Imports get_conn, insert_row, is_configured from supabase_client
2. Has a write_result(run_id, result) function that inserts into table module_X_outputs
3. Has a write_run_log(run_id, ...) function for module_X_run_logs

Then at the end of agent.py, add a try/except block that:
- Imports is_configured from supabase_client
- Only writes if is_configured() returns True
- Prints "[DB] Supabase sync complete" on success
- Prints "[DB WARN] Supabase sync skipped: {error}" on failure
```

### Query Module 2 shortlists from Supabase

```
Using psycopg2 and supabase_client.get_conn(), write a function that:
1. Queries module2_trend_shortlist for the latest run_id
2. Returns shortlisted trends sorted by rank
3. Joins with module1_trend_objects on trend_id to get full evidence
```

### Add a new table for a module

```
Add a new table to db/migrations/moduleX.sql for storing [describe what you want].
Follow the existing pattern: BIGSERIAL PRIMARY KEY, run_id TEXT NOT NULL,
relevant JSONB columns, timestamps. Use IF NOT EXISTS. Then update
module_X/supabase_writer.py to write to it.
```

### Run migrations dry-run to preview SQL

```bash
python3 db/setup.py --dry-run
```

---

## Module Overview

### Module 1 — XHS Trend Object Builder
Scrapes Xiaohongshu live using Chrome automation. Keeps all post content raw and unchanged. Anonymizes creator names (SHA-256 hash). AI-captions images. Clusters posts into Trend Objects with engagement metrics, visual assets, and anonymized comment signals.

**XHS keywords for Louis Vuitton:** `Louis Vuitton` `LV` `路易威登` `LV包包` `LV穿搭` plus trend terms like `静奢` `通勤包` as needed

### Module 2 — Trend Relevance & Materiality Filter
Two-stage filter: deterministic pre-filter (no LLM cost) → LLM brand-fit scoring → top 5 shortlist. Outputs a `trend_shortlist.json` directly into Module 3's folder so the pipeline is fully automated.

### Module 3 — CA Trend Brief Agent
Takes the Module 2 shortlist and generates formatted trend briefing cards (markdown) for Client Advisors, with city-specific tone (Shanghai vs Beijing), evidence-grounded reasoning, and suggested opening lines.

### Module 4 — Client Memory Structurer
Converts sales advisor voice memos or text notes into structured client memory objects: life events, budgets, aesthetic preferences, mood signals, and next-step intent. Uses OpenRouter.

### Module 5 — Outreach Angle Agent
Reads client memory + trend shortlist and generates personalized outreach angles and WeChat message drafts for Client Advisors to use directly in client conversations.
