# Deliverable 1 — Module 1 package

## What this satisfies (instructor rubric)

| Requirement | Module 1 status |
|-------------|-----------------|
| Real XHS market data | `data/xhs_posts.json` — March–April 2026 window (see `run_config`); **55** posts after filter; unfiltered backup `data/xhs_posts_before_date_filter.json` (**200** posts) |
| ≥200 posts | **Re-scrape + filter** until ≥200 posts fall in March–April (see `WEEK11_DATE_FILTER.md`) |
| ≥30 trend objects | **50** in latest run (`outputs/runs/run_0038_trend_objects.json` as of Mar–Apr 2026 filter); `run_config.json` uses semantic clustering + `min_posts_per_trend` / `top_k_trends` |
| Save input dataset ID + date range | **`deliverables/week11_batch_meta.json`** |
| Save outputs | Paths listed in meta JSON |
| Save run log / trace | `outputs/runs/run_0038_run_log.json` + `run_0038_trace.log` |

## Files to zip or submit

1. `deliverables/week11_batch_meta.json`
2. `data/xhs_posts.json` (or a checksum + path if repo-only)
3. `outputs/runs/run_0038_trend_objects.json`
4. `outputs/runs/run_0038_run_log.json`
5. `outputs/runs/run_0038_trace.log` (optional but good “trace”)

## Next (Modules 2–3 — same Deliverable 1)

From repo root:

```bash
python3 module_2/agent.py
# set M3_TOP_N=10 in .env, then:
python3 module_3/trend_brief_agent/agent.py --brand "Louis Vuitton" --city "Shanghai" --top-n 10
```

Archive Module 2/3 outputs + their `run_log.json` alongside this folder.
