# Agent Pipeline — Modules 1–5

A sequential multi-module AI agent pipeline that scrapes Xiaohongshu (XHS) trends, structures client memory, generates outreach, and persists everything to Supabase automatically.

**Live repo:** [github.com/m-ny/mvp](https://github.com/m-ny/mvp)

---

## Project Structure

```
Agent/
├── main.py                  ← runs all modules in order (1→5)
├── config.py                ← global API key + model loader
├── supabase_client.py       ← shared Postgres connection factory
├── requirements.txt
├── .env.example             ← copy to .env and fill in secrets
│
├── db/
│   ├── setup.py             ← creates all Supabase tables
│   └── migrations/
│       ├── module1.sql      ← XHS posts + trend objects + run logs
│       ├── module3.sql      ← trend briefs
│       ├── module4.sql      ← client memory objects
│       └── module5.sql      ← outreach suggestions
│
├── module_1/                ← XHS Trend Object Builder
│   ├── xhs_scraper_live.py  ← live XHS scraper (Chrome + DrissionPage)
│   ├── xhs_trend_builder.py ← clusters posts → trend objects
│   └── supabase_writer.py   ← writes posts + trends + logs to DB
│
├── module_3/trend_brief_agent/
│   ├── agent.py             ← generates trend briefs (Anthropic/OpenRouter)
│   └── supabase_writer.py
│
├── module_4/
│   ├── First_Run.py         ← voice memo → structured client memory
│   └── supabase_writer.py
│
└── module_5/
    ├── agent.py             ← outreach angle + WeChat draft generator
    └── supabase_writer.py
```

---

## Quick Start

### 1. Install dependencies

```bash
pip3 install -r requirements.txt
```

For module 1 live scraping (needs a virtual env on Mac):
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

Runs all 4 migration files. Safe to re-run — uses `IF NOT EXISTS` everywhere.

To only set up one module:
```bash
python3 db/setup.py --module 1
```

### 4. Run the full pipeline

```bash
python3 main.py
```

Or run individual modules:
```bash
# Module 1 — scrape XHS then build trend objects
cd module_1
.venv/bin/python3 xhs_scraper_live.py --keywords "LV" "Chanel" "Dior" --times 3
.venv/bin/python3 xhs_trend_builder.py

# Module 3 — generate trend briefs
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

## Supabase Schema — One Table Group Per Module

Each module owns its own tables. They never share tables across modules.

### Module 1 — XHS Trend Object Builder

| Table | What it stores |
|---|---|
| `module1_xhs_posts` | Every scraped/processed XHS post. Raw titles, captions, hashtags unchanged. Anonymized creator IDs. All image URLs. AI image captions. Full comment + reply text (commenter names hashed). |
| `module1_trend_objects` | Each trend cluster: label, summary, AI reasoning, confidence, evidence posts, engagement metrics, image URLs, and all anonymized comment signals. |
| `module1_run_logs` | One row per pipeline run. Records, LLM config, keywords, timing. |

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

You can check what was written in the Supabase dashboard → Table Editor.

---

## AI Prompts — use these with Cursor / Claude to extend the pipeline

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

### Add a new table for a module

```
Add a new table to db/migrations/moduleX.sql for storing [describe what you want].
Follow the existing pattern: BIGSERIAL PRIMARY KEY, run_id TEXT NOT NULL,
relevant JSONB columns, timestamps. Use IF NOT EXISTS. Then update
module_X/supabase_writer.py to write to it.
```

### Query trends from Supabase in Python

```
Using psycopg2 and the connection from supabase_client.get_conn(),
write a function that:
1. Queries module1_trend_objects for the latest run_id
2. Returns all trend objects with confidence = 'high'
3. Includes their comment_signals JSONB parsed as a Python dict
```

### Run migrations dry-run to preview SQL

```bash
python3 db/setup.py --dry-run
```

---

## Module Overview

### Module 1 — XHS Trend Object Builder
Scrapes Xiaohongshu live using Chrome automation. Keeps all post content raw and unchanged. Anonymizes creator names (SHA-256 hash). AI-captions images. Clusters posts into Trend Objects with engagement metrics, visual assets, and anonymized comment signals.

### Module 2 — (Placeholder)
Reserved for a future pipeline step.

### Module 3 — Trend Brief Agent
Takes trend objects and generates formatted trend briefs (markdown + HTML) for a given brand and city.

### Module 4 — Client Memory Structurer
Converts sales advisor voice memos into structured client memory objects: life events, budgets, aesthetic preferences, mood, and next-step intent. Uses OpenRouter.

### Module 5 — Outreach Angle Agent
Reads client memory + trend shortlist and generates personalized outreach angles and WeChat message drafts for client advisors.
