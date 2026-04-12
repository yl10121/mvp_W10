# Fail case — Module 1 — 2026-03-28

## What failed (one sentence)

Module 1 ran with LLM labeling enabled in config, but **`OPENROUTER_API_KEY` was not set in the environment**, so all 30 trends fell back to **heuristic labels**—producing many duplicate labels like “Luxury Handbag & Leather Goods” and “Mixed Trend Signals” that do not distinguish real XHS discourse patterns for CAs.

## Fix we will try next week (one sentence)

**Set `OPENROUTER_API_KEY` in `.env` (or export it) before running `xhs_trend_builder.py`** so LLM cluster labels run, and add a **post-pass dedupe warning** when `labeling_source` is all `heuristic` and label cardinality is below a threshold.

## Reference artifacts

- Terminal excerpt captured in [`screenshot.png`](./screenshot.png) (same run as `module_1/outputs/runs/run_0036_trace.log`).
- Full JSON: [`module_1/outputs/runs/run_0036_trend_objects.json`](../module_1/outputs/runs/run_0036_trend_objects.json) — see `decision_logic.llm_errors`.
- Automated QA: [`module_1/outputs/EVAL_REPORT.md`](../module_1/outputs/EVAL_REPORT.md) (duplication / distinctness checks **failed** for this run — consistent with heuristic-only labels).
