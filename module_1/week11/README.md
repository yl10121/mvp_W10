# Module 1 — Week 11 package

Everything for **Week 11 Module 1** lives here or is linked below. Use this folder as a **single place to review or zip** for submission (large JSON stays under `module_1/data/` and `module_1/outputs/` — copy those paths when archiving).

## Start here

| Doc | Purpose |
|-----|---------|
| [`ASSIGNMENT.md`](./ASSIGNMENT.md) | Short instructor rubric (D1–D4) |
| [`DELIVERABLE_1_README.md`](./DELIVERABLE_1_README.md) | Deliverable 1 checklist + file list |
| [`DELIVERABLE_2_3_EXTRACT.md`](./DELIVERABLE_2_3_EXTRACT.md) | Deliverables 2 & 3 — sessions + quotes |
| [`failure_notes.md`](./failure_notes.md) | Deliverable 4 — fail case text |
| [`week11_batch_meta.json`](./week11_batch_meta.json) | Dataset ID, counts, output paths (machine-readable) |

## Deliverable 1 — Data & run outputs (large files)

| Artifact | Path (from repo root) |
|----------|------------------------|
| Input posts (200) | [`module_1/data/xhs_posts.json`](../data/xhs_posts.json) |
| Run config | [`module_1/data/run_config.json`](../data/run_config.json) |
| Trend objects (30), run `run_0036` | [`module_1/outputs/runs/run_0036_trend_objects.json`](../outputs/runs/run_0036_trend_objects.json) |
| Run log | [`module_1/outputs/runs/run_0036_run_log.json`](../outputs/runs/run_0036_run_log.json) |
| CLI trace | [`module_1/outputs/runs/run_0036_trace.log`](../outputs/runs/run_0036_trace.log) |
| Latest copies | [`module_1/outputs/trend_objects.json`](../outputs/trend_objects.json), [`module_1/outputs/run_log.json`](../outputs/run_log.json) |
| Eval report (QA) | [`module_1/outputs/EVAL_REPORT.md`](../outputs/EVAL_REPORT.md) |

**Reproduce run** (from `module_1/`):

```bash
../.venv/bin/python3 xhs_trend_builder.py
```

Set `OPENROUTER_API_KEY` in `.env` for LLM trend labels (see fail case if missing).

## Deliverables 2 & 3 — Reviewers + CSV

| Artifact | Path |
|----------|------|
| Module 1 rows only | [`feedback_log_module1.csv`](./feedback_log_module1.csv) |
| Full team CSV (root) | [`feedback_log.csv`](../../feedback_log.csv) |
| Transcripts | [`interviews/tiffany.md`](./interviews/tiffany.md), [`interviews/stone-island.md`](./interviews/stone-island.md) |

## Deliverable 4 — Fail case pack

| Artifact | Path |
|----------|------|
| Notes | [`failure_notes.md`](./failure_notes.md) |
| Screenshot | [`screenshot.png`](./screenshot.png) |
| Canonical copy (repo root) | [`fail_case_pack/`](../../fail_case_pack/) |

## Code & spec (reference)

| Item | Path |
|------|------|
| Trend builder | [`../xhs_trend_builder.py`](../xhs_trend_builder.py) |
| Week 11 improvements spec | [`../SPEC_WEEK11_IMPROVEMENTS.md`](../SPEC_WEEK11_IMPROVEMENTS.md) |

## Zip hint

From repo root, example archive contents:

- `module_1/week11/**` (this folder)
- `module_1/data/xhs_posts.json`
- `module_1/outputs/runs/run_0036_*.json`, `run_0036_trace.log`

---

*See also [`../../WEEK11_ASSIGNMENT_COMPLETE.md`](../../WEEK11_ASSIGNMENT_COMPLETE.md) for the full assignment log and team scope.*
