# IO_CONTRACT.md — Module 2: Trend Relevance & Materiality Filter

## Inputs

**Input table(s):** `module_1/outputs/runs/run_*_trend_objects.json` (all files via glob; beauty category skipped)

**Required fields:**
- `trend_id` — unique trend identifier (namespaced with run ID at load time)
- `label` — trend name, used for taboo screening and LLM prompt
- `category` — must match an entry in `brand_profile_celine.json` active_categories
- `summary` — 1–3 sentence description, used for taboo screening and LLM context
- `evidence.posts[].date` — ISO 8601 date, used for freshness pre-filter (must be within 21 days)
- `metrics.total_engagement` — minimum 3000 required by pre-filter

**Optional fields:**
- `location` — source city; defaults to "China" if missing
- `metrics.post_count` — used for pre-filter (luxury_fashion: 2–4 passes with low_signal warning; <2 rejected)
- `evidence.snippets` — minimum 2 required; used as LLM evidence grounding

**Assumptions:**
1. `brand_profile_celine.json` exists with `active_categories` and `brand_taboos` fields
2. `OPENROUTER_API_KEY` is set in root `.env` before LLM evaluation runs
3. Supabase is optional — agent always completes and saves locally if DB is unreachable

---

## Outputs

**Output table(s):** `module2_trend_shortlist` (one row per shortlisted trend), `module2_run_logs` (one row per run)

**Required fields:**
- `trend_id` — namespaced ID (e.g. `run_0011_t01`, `synthetic_t03`)
- `label` — trend name
- `category` — product category
- `composite_score` — weighted LLM score 0–10; threshold ≥ 6.5 to shortlist
- `data_type` — `"real"` or `"synthetic"` — tracks data provenance
- `location` — source city or region; defaults to "China"

**Evidence fields:**
- `why_selected` — LLM reasoning grounded in XHS evidence (3–5 sentences)
- `evidence_references` — direct quotes or metrics cited by LLM
- `metric_signal` — total_engagement, post_count, avg_engagement from Module 1

**Confidence field:** `confidence` — LLM-assigned string: `"high"`, `"medium"`, or `"low"`; written to both JSON outputs and Supabase column
