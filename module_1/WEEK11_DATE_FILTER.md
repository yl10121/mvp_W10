# March–April 2026 date filter + clustering (Module 1)

## What changed

1. **`data/run_config.json`**
   - `time_window`: `2026-03-01` … `2026-04-30`

   - `xhs_reference_date_iso`: `2026-03-30` (anchors “昨天”, “N天前”, and MM-DD without year)

   - **Clustering:** `cluster_min_jaccard` / `cluster_min_token_overlap` tuned for more, smaller clusters; `min_posts_per_trend` set to **1** so singleton posts still become trends (more distinct objects at the cost of weaker per-trend evidence).

   - `top_k_trends`: **120** cap.

2. **`xhs_trend_builder.py`**
   - Date parsing now handles **`编辑于 …`** (e.g. `编辑于 03-11 上海`, `编辑于 2025-11-09`).
   - `post_matches_filters` uses **`normalize_xhs_date`** (not `parse_iso_date` only) and **excludes** posts with no parseable date when a time window is set.

3. **`filter_posts_by_config.py`**
   - One-time backup: `data/xhs_posts_before_date_filter.json`
   - Rewrites `data/xhs_posts.json` to posts that pass the same window as the trend builder.

## Re-scrape “only March–April”

The live scraper does not yet filter by calendar in the browser. **Workflow:** run `xhs_scraper_live.py` with your keywords, then run **`filter_posts_by_config.py`** so `xhs_posts.json` matches March–April. To reach **≥200 posts** in-window, increase scroll depth / runs until enough notes fall in the window (check `date` on each note).

## Restore the pre-filter 200-post file

```bash
cd module_1/data
cp xhs_posts_before_date_filter.json xhs_posts.json
```

Then remove or adjust `time_window` in `run_config.json` if you want to analyze the full year again.
