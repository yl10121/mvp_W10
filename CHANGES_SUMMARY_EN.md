# Summary of Changes 

A concise overview of recent work on this repo: unified LLM configuration, Module 5 data flow, brand-catalog RAG, database setup, and repository hygiene.

---

## LLM & configuration

- `**config.py**` loads `.env` from the **repository root** and, when `OPENROUTER_API_KEY` is set and `OPENAI_API_KEY` is empty, **mirrors** the key into `OPENAI_API_KEY` so OpenAI-compatible clients (e.g. Module 1 trend builder) work with a **single key**.
- **Entry scripts** import `config` after adding the repo root to `sys.path` (Modules 1–5, `pipeline_inputs.py`, `translate_logs.py`, `eval_agent.py`, `web_ca.py`, etc.) so the same rule applies when running scripts directly.
- `**main.py`** still passes `OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `DEFAULT_MODEL`, and `BRAND` into subprocesses; uses absolute `script_path` and correct `workdir` (including nested Module 3 path). Module 3 is invoked with `--brand` and `--city` flags.
- **Module 5 `call_llm`**: prefers **OpenRouter** when `OPENROUTER_API_KEY` is set (or base URL points at OpenRouter); otherwise **Anthropic** native API. `**eval_agent.py`** / `**translate_logs.py**` follow the same pattern where applicable.
- `**.env.example**` documents the “one key” setup and Module 5 / catalog RAG env vars.

---

## Module 5 — inputs, trend “KB”, and catalog RAG

- `**pipeline_inputs.py**`: loads M5 inputs from **Supabase only** (M2 shortlist + M4 client summaries); pins runs via env; applies `**M5_TREND_TOP_N`** (default cap when unset).
- `**trend_kb.py**`: builds a **read-only** trend block for the prompt (`M5_TREND_KB_MODE`: `compact` vs `full`) — **shaping** the same batch, not vector retrieval.
- `**catalog_rag.py`**: **RAG** over `module1_brand_products` — builds a query from **client memory + trend KB**, calls **OpenRouter `/v1/embeddings`**, scores by **cosine similarity**, returns **Top-K** SKUs; on failure, falls back to **lexical** overlap.
- `**agent.py`**: injects the RAG catalog section into the user prompt; `**trace.catalog_rag**` records method and scores; optional legacy mode via `**M5_CATALOG_RAG=0**` (truncated full list).
- `**supabase_reader.py**` / `**web_ca.py**`: aligned with M4 full-row fetch by PK (`memory_row_id`, `m4_run_id`) where needed.

---

## Database & Module 1 catalog

- `**db/migrations/module1_brand_products.sql**`: defines `**module1_brand_products**`.
- `**db/setup.py**`: after `module1.sql`, runs `**module1_brand_products.sql**` via `**MODULE_EXTRA_FILES**`.
- `**module_1/seed_brand_products.py**`, `**supabase_reader.read_brand_products**`, `**supabase_writer.upsert_brand_products**`: seed and read/write the catalog.
- **M2 / M4 migrations and writers** (as in repo): extended columns for shortlist and client memories where applicable.

---

## Repository hygiene

- `**.gitignore`**: ignores `.env*`, build caches, Playwright/XHS scraper paths, `**module_1/outputs/**`, `**module_2/outputs/**`, local `**run_log.json**` files under M4/M5, and root `***.pdf**`.
- **Stopped tracking** generated JSON/logs that had been committed under `module_1/outputs/`, `module_2/outputs/`, and `module_5/run_log.json` — artifacts are expected to be reproduced locally.

---

## Documentation

- `**module_5/MODULE5_架构说明_产品经理版.md`**: product-facing explanation of data flow, **trend KB vs RAG**, and env toggles (Chinese).

---

## Operational notes

- After pulling, **re-run Module 1** (and downstream steps) if you need fresh files under `module_1/outputs/`; they are no longer in Git.
- Set `**DEFAULT_MODEL`** to a valid **OpenRouter model id** when using only `OPENROUTER_API_KEY`.

