#!/usr/bin/env python3
"""Print how many posts match run_config.json (brand + category + March–April date window)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from xhs_trend_builder import (  # noqa: E402
    normalize_posts,
    post_matches_filters,
    read_json,
)


def main() -> None:
    posts_path = HERE / "data" / "xhs_posts.json"
    config_path = HERE / "data" / "run_config.json"
    raw = read_json(posts_path)
    config = read_json(config_path)
    posts = normalize_posts(raw if isinstance(raw, list) else [])
    tw = config.get("time_window") or {}
    n = sum(1 for p in posts if post_matches_filters(p, config))
    print(
        f"Posts matching run_config (brand + category + {tw.get('start_date')}..{tw.get('end_date')}): "
        f"{n} / {len(posts)} loaded"
    )


if __name__ == "__main__":
    main()
