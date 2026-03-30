# Module 2 — Data Card

**Part A2 of Week 10 Assignment**

---

## Data Source

- **Platform:** Xiaohongshu (XHS / RedNote)
- **Scraped by:** Module 1 — XHS Trend Object Builder
- **Storage location:** `module_1/outputs/runs/run_XXXX_trend_objects.json`
- **Loaded by:** `module_2/agent.py` via glob on `run_*_trend_objects.json`

---

## Brand & Category

- **Brand:** Celine
- **Category:** luxury_fashion (runs 0009–0013), beauty (runs 0001–0008, skipped)
- **Location coverage:** All China cities. Location captured per trend object where available; defaults to "China" if missing. Location is passed through to Module 3 to enable per-city analysis.

---

## Date Range

- **Earliest start date across all run files:** 2026-01-01
- **Latest end date across all run files:** 2026-03-31
- **Source:** `time_window.start_date` and `time_window.end_date` fields read from actual run files

---

## Volume Counts

- **Number of run files loaded:** 13
- **Total trend objects in batch:** 40 (after beauty skipped) + 25 synthetic = 40 input to filter
- **Breakdown by run:**
  - runs 0001–0008: 5 trend objects each (beauty category, skipped — not relevant for Celine)
  - runs 0009–0013: 3 trend objects each (luxury_fashion category, Celine-specific XHS posts) = 15 real luxury_fashion trends

---

## Shortlisted Count

**15 trends shortlisted.** Written to Supabase table `module2_trend_shortlist` (15 rows) and `module2_run_logs`. Also saved locally to `module_2/outputs/output_shortlist.json` and `module_3/trend_brief_agent/trend_shortlist.json`.

---

## Real vs Synthetic Breakdown

| Source | Count | Data Type | Category | Notes |
|--------|-------|-----------|----------|-------|
| module_1/outputs/runs/run_0001 to run_0008 | 40 objects (5 per run) | **Real XHS** | beauty | **Skipped** — beauty category not relevant for Celine; excluded before batch |
| module_1/outputs/runs/run_0009 to run_0013 | 15 objects (3 per run) | **Real XHS** | luxury_fashion | Celine-specific XHS scrape across 5 runs; same 3 underlying posts repeated |
| module_2/data/synthetic_trends.json | 25 objects | **Synthetic** | luxury_fashion | Hand-constructed Celine-relevant trend objects for batch testing; tagged `data_type: synthetic` on every object |
| **Total input to filter** | **40 objects** | Mixed | — | 15 real + 25 synthetic; agent.py prints real vs synthetic count at load time |

Each trend object carries a `data_type` field (`"real"` or `"synthetic"`) that is:
- Passed through to `output_shortlist.json`
- Written into the Supabase `module2_trend_shortlist` table as a dedicated column
- Included in `module_3/trend_brief_agent/trend_shortlist.json`

This allows the database and downstream modules to filter by data provenance at any time.

---

## Known Constraints

1. **No image URLs captured** in current real runs — scraping ran with `--no-detail` flag due to XHS rate limiting.
2. **No comments scraped** — `--no-detail` also skips comment data; comment_count fields are zero in real runs.
3. **LLM labeling fell back to heuristic** in some runs due to missing `OPENROUTER_API_KEY` at time of Module 1 scrape (see `decision_logic.llm_errors` in run log files).
4. **No cross-city identity linking** — creator handles are SHA-256 hashed; no cross-city or cross-run user identity resolution is performed.
5. **Runs 0001–0008 are near-duplicates** — generated from the same beauty post dataset; they increase batch volume but add limited trend diversity for Celine evaluation.
6. **Synthetic trends are for testing only** — all 25 synthetic objects are clearly marked and should not be presented as real XHS signal to end users or in client-facing outputs.
