# Module 5 — I/O Contract (Supabase Schema)

## Architecture

```
Module 2 ──→ module2_trend_shortlist ──┐
                                       ├──→ Module 5 Agent ──→ module5_outreach_suggestions
Module 4 ──→ module4_client_memories ──┘                   ──→ module5_run_logs
```

Module 5 **reads** from two upstream tables and **writes** to two output tables.
All tables live in the shared Supabase (PostgreSQL) instance.

---

## Inputs

### Table: `module2_trend_shortlist`

Written by Module 2. Module 5 reads the latest `run_id` (or pinned via `M5_MODULE2_RUN_ID`).

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `id` | serial | auto | PK |
| `run_id` | text | ✅ | Module 2 run identifier |
| `trend_id` | text | ✅ | Unique trend ID (e.g. `T_B01`) |
| `rank` | integer | ✅ | Shortlist rank (1 = top) |
| `label` | text | ✅ | Human-readable trend name |
| `category` | text | ✅ | Product category (e.g. `leather_goods`, `ready-to-wear`) |
| `composite_score` | numeric | ✅ | Weighted score (0–10) |
| `score_freshness` | numeric | | Sub-score |
| `score_brand_fit` | numeric | | Sub-score |
| `score_category_fit` | numeric | | Sub-score |
| `score_materiality` | numeric | | Sub-score |
| `score_actionability` | numeric | | Sub-score |
| `confidence` | text | ✅ | `high` / `medium` / `low` |
| `why_selected` | text | | Reason for shortlisting |
| `evidence_references` | jsonb | | Array of source citations |
| `metric_signal` | jsonb | | Engagement / volume metrics |
| `brand` | text | | Brand name (e.g. `Celine`) |
| `module1_run_id` | text | | Upstream Module 1 run ID |
| `created_at` | timestamptz | auto | Row creation time |

**Assumptions**: At least 5 trends per run. `run_id` groups a single shortlist batch.

### Table: `module4_client_memories`

Written by Module 4. Module 5 reads the latest `run_id` (or pinned via `M5_MODULE4_RUN_ID`).

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `id` | serial | auto | PK |
| `run_id` | text | ✅ | Module 4 run identifier |
| `raw_voice_note` | text | ✅ | Original CA voice memo transcript |
| `summary` | text | ✅ | One-line structured summary |
| `life_event` | jsonb | ✅ | `{value, confidence, evidence}` |
| `timeline` | jsonb | ✅ | `{value, confidence, evidence}` |
| `aesthetic_preference` | jsonb | ✅ | `{value, confidence, evidence}` |
| `size_height` | jsonb | | `{value, confidence, evidence}` |
| `budget` | jsonb | | `{value, confidence, evidence}` |
| `mood` | jsonb | | `{value, confidence, evidence}` |
| `trend_signals` | jsonb | | `{value, confidence, evidence}` |
| `next_step_intent` | jsonb | ✅ | `{value, confidence, evidence}` |
| `model_used` | text | | LLM model that produced the memory |
| `confidence_summary` | jsonb | | `{High: n, Medium: n, Low: n}` |
| `missing_fields_count` | integer | | Count of fields with no data |
| `generated_at` | timestamptz | auto | Row creation time |

**Assumptions**: Each row = one client memory. `run_id` groups a batch. At least `summary`, `life_event`, `aesthetic_preference`, and `next_step_intent` must be populated for M5 to produce meaningful output.

---

## Outputs

### Table: `module5_outreach_suggestions`

One row per client per run. This is the primary deliverable.

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `id` | serial | auto | PK |
| `run_id` | text | ✅ | Module 5 run identifier |
| `client_id` | text | ✅ | Client identifier (matches M4 input) |
| `outreach_angle` | text | ✅ | Best angle label (e.g. "艺术周静奢造型预约") |
| `wechat_draft` | text | ✅ | Primary WeChat message draft |
| `reasoning` | text | ✅ | **Evidence**: angle_summary explaining why this angle was chosen |
| `trend_signals_used` | jsonb | ✅ | **Evidence**: array of `evidence_used` strings citing memory fields + trend IDs |
| `client_memory_ref` | jsonb | ✅ | **Evidence**: `{client_id, trend_ids[], evidence_used[]}` — traceable back to input tables |
| `confidence` | text | ✅ | `high` / `medium` / `low` — agent's self-assessed confidence |
| `model_used` | text | ✅ | LLM model identifier |
| `created_at` | timestamptz | auto | Row creation time |

**Evidence fields** (required for traceability):
- `trend_signals_used` — which trend IDs and memory fields were cited
- `client_memory_ref` — links back to input client_id and trend_ids
- `reasoning` — natural-language explanation of the outreach angle
- `confidence` — agent's self-assessed output quality

### Table: `module5_run_logs`

One row per batch run. Metadata for debugging and evaluation.

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `id` | serial | auto | PK |
| `run_id` | text | ✅ | Module 5 run identifier |
| `client_id` | text | | First client in batch (for quick lookup) |
| `model_used` | text | ✅ | LLM model |
| `prompt_version` | text | ✅ | System prompt version (e.g. `v2`) |
| `suggestions_count` | integer | ✅ | Number of outreach suggestions generated |
| `run_log_raw` | jsonb | | Full run log JSON (for debugging) |
| `created_at` | timestamptz | auto | Row creation time |

---

## Field Count Summary

| Table | Total columns | Required | Evidence columns |
|-------|--------------|----------|-----------------|
| `module5_outreach_suggestions` | 10 | 9 | 4 (`reasoning`, `trend_signals_used`, `client_memory_ref`, `confidence`) |
| `module5_run_logs` | 7 | 5 | 1 (`run_log_raw`) |

Total unique fields across output tables: **15** (within the ≤15 target).

---

## Env Variables for Integration

| Variable | Purpose | Example |
|----------|---------|---------|
| `M5_SOURCE` | Set to `supabase` to read from DB | `supabase` |
| `M5_MODULE2_RUN_ID` | Pin a specific M2 run | `bench_m2_x` |
| `M5_MODULE4_RUN_ID` | Pin a specific M4 run | `bench_m4_20260330` |
| `SUPABASE_PASSWORD` | DB credential | *(in .env)* |
| `M5_TREND_TOP_N` | Limit trends to top N | `5` |

## How to Populate Sample Rows

```bash
# 1. Seed M2 trends + M4 client memories into Supabase
python3 module_5/seed_supabase.py --m2 --m4

# 2. Run Module 5 reading from Supabase → writes outreach suggestions back
M5_SOURCE=supabase python3 module_5/agent.py --all

# 3. Or seed existing run_log.json directly (without re-running LLM)
python3 module_5/seed_outreach_to_supabase.py
```
