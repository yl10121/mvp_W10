#!/usr/bin/env bash
# Scrape Tiffany-focused XHS posts WITH detail pages (dates for March–April filter).
# Goal: enough posts that after filter_posts_by_config.py you have strong in-window rows.
#
# Detail is ON by default (do not pass --no-detail).
#
# Usage:
#   ./run_tiffany_scrape.sh              # fresh run (backs up existing xhs_posts.json once)
#   ./run_tiffany_scrape.sh --append     # merge new posts (dedupe by post_link), new IDs
#
# Then:
#   ../.venv/bin/python3 filter_posts_by_config.py
#   ../.venv/bin/python3 report_date_window.py
#   ../.venv/bin/python3 xhs_trend_builder.py

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${ROOT}/.venv/bin/python3"
cd "${ROOT}/module_1"

if [[ "${1:-}" == "--append" ]]; then
  APPEND_FLAG=(--append)
else
  APPEND_FLAG=()
  if [[ -f data/xhs_posts.json ]]; then
    cp -f data/xhs_posts.json "data/xhs_posts_backup_before_scrape.json"
    echo "[backup] data/xhs_posts_backup_before_scrape.json"
  fi
fi

# With set -u, "${empty_array[@]}" errors on some Bash versions; only pass --append when set.
SCRAPER_ARGS=(
  xhs_scraper_live.py
  -k "Tiffany" "蒂芙尼" "Tiffany T" "蒂芙尼戒指" "Knot" "Lock" "HardWear" "六爪钻戒" "蓝盒子" "Atlas"
  --times 7
  --max-posts 380
  --fast
  --no-caption
  --skip-comments
  -c luxury_fashion
)
[[ ${#APPEND_FLAG[@]} -gt 0 ]] && SCRAPER_ARGS+=("${APPEND_FLAG[@]}")
exec "${PY}" "${SCRAPER_ARGS[@]}"
