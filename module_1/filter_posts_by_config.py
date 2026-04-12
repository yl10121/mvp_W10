#!/usr/bin/env python3
"""Filter module_1/data/xhs_posts.json to match run_config time_window (e.g. March–April only).

Backs up the current file to data/xhs_posts_before_date_filter.json once, then overwrites
xhs_posts.json with posts that pass post_matches_filters (same logic as xhs_trend_builder).

Usage (from module_1/):
  ../.venv/bin/python3 filter_posts_by_config.py
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from xhs_trend_builder import (
    normalize_posts,
    post_matches_filters,
    read_json,
)


def main() -> None:
    here = Path(__file__).resolve().parent
    data_dir = here / "data"
    posts_path = data_dir / "xhs_posts.json"
    config_path = data_dir / "run_config.json"
    backup_path = data_dir / "xhs_posts_before_date_filter.json"

    raw = read_json(posts_path)
    if not isinstance(raw, list):
        raise SystemExit("xhs_posts.json must be a JSON array")
    config = read_json(config_path)
    posts = normalize_posts(raw)
    allowed = {p.post_id for p in posts if post_matches_filters(p, config)}
    filtered = [item for item in raw if str(item.get("post_id", "")) in allowed]

    if not backup_path.exists():
        shutil.copy2(posts_path, backup_path)
        print(f"[backup] {backup_path.name} (one-time copy of pre-filter corpus)")

    with posts_path.open("w", encoding="utf-8") as f:
        json.dump(filtered, f, ensure_ascii=False, indent=2)

    tw = config.get("time_window") or {}
    print(
        f"[done] Kept {len(filtered)} / {len(raw)} posts "
        f"(window {tw.get('start_date')} .. {tw.get('end_date')})"
    )


if __name__ == "__main__":
    main()
