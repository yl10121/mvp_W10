# Deliverable 1 — Module 1 package (Week 11)

Paths below are from the **`module_1/`** directory (repo root = parent of `module_1/`).

## What this satisfies (instructor rubric)

| Requirement | Module 1 status |
|-------------|-----------------|
| Real XHS market data | [`../data/xhs_posts.json`](../data/xhs_posts.json) — **200** posts |
| ≥200 posts | **200** |
| ≥30 trend objects | **30** in [`../outputs/runs/run_0036_trend_objects.json`](../outputs/runs/run_0036_trend_objects.json) (see [`../data/run_config.json`](../data/run_config.json): `force_equal_engagement_bins`) |
| Save input dataset ID + date range | [`week11_batch_meta.json`](./week11_batch_meta.json) (copy; canonical also under [`../deliverables/week11_batch_meta.json`](../deliverables/week11_batch_meta.json)) |
| Save outputs | Paths listed in meta JSON |
| Save run log / trace | [`../outputs/runs/run_0036_run_log.json`](../outputs/runs/run_0036_run_log.json) + [`../outputs/runs/run_0036_trace.log`](../outputs/runs/run_0036_trace.log) |

## Files to zip or submit

1. `module_1/week11/week11_batch_meta.json` (this folder)
2. `module_1/data/xhs_posts.json`
3. `module_1/outputs/runs/run_0036_trend_objects.json`
4. `module_1/outputs/runs/run_0036_run_log.json`
5. `module_1/outputs/runs/run_0036_trace.log` (optional but good “trace”)

## Next (Modules 2–3 — same Deliverable 1, team)

From repo root:

```bash
python3 module_2/agent.py
# set M3_TOP_N=10 in .env, then:
python3 module_3/trend_brief_agent/agent.py --brand "Celine" --city "Shanghai" --top-n 10
```

Archive Module 2/3 outputs + their `run_log.json` alongside this folder.
