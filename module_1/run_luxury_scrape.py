#!/usr/bin/env python3
"""
Multi-brand luxury scraper launcher -- scrapes XHS with brand-specific AND
trend-descriptive keywords using Playwright.

Implements SPEC_WEEK11_IMPROVEMENTS.md sections 1 (Competitor Scraping) and
8 (Better Scraping Keywords).

Run from module_1/:  .venv/bin/python3 run_luxury_scrape.py

Chrome will open -> scan the QR code with your XHS app -> scraping starts.
Login cookies are saved so you only need to scan once.
"""

import os
from pathlib import Path

PYTHON = str(Path(__file__).parent / ".venv" / "bin" / "python3")
SCRAPER = str(Path(__file__).parent / "xhs_scraper_pw.py")

# ---------------------------------------------------------------------------
# 1) Brand keywords -- organised by brand
# ---------------------------------------------------------------------------
BRAND_KEYWORDS: dict[str, list[str]] = {
    "Celine": [
        "Celine", "Celine穿搭", "Celine包包",
        "Celine Triomphe", "Celine Box",
        "赛琳穿搭", "赛琳包",
    ],
    "Dior": [
        "Dior穿搭", "Dior包包", "Dior秀场", "迪奥",
    ],
    "Louis Vuitton": [
        "LV穿搭", "LV包包", "路易威登",
    ],
    "Loewe": [
        "Loewe穿搭", "Loewe包包", "罗意威",
    ],
    "Chanel": [
        "Chanel穿搭", "Chanel包包", "香奈儿",
    ],
    "Bottega Veneta": [
        "BV穿搭", "BV包包", "葆蝶家",
    ],
}

# ---------------------------------------------------------------------------
# 2) Trend-descriptive keywords (no brand name)
# ---------------------------------------------------------------------------
TREND_KEYWORDS: list[str] = [
    # Quiet luxury / old money
    "静奢风", "老钱风穿搭", "quiet luxury", "低调奢华",
    # Minimalist styling
    "极简穿搭", "高级感穿搭", "胶囊衣橱",
    # Investment pieces
    "值得入的包", "经典款不过时", "保值包包",
    # Bag nostalgia / relevance
    "时代的眼泪", "还值得买吗", "经典还是过时",
    # Commute / work luxury
    "通勤包推荐", "职场穿搭", "通勤神器",
    # French / Parisian style
    "法式穿搭", "巴黎风", "法式优雅",
    # Secondhand / resale
    "二手奢侈品", "中古包", "回收行情",
    # Celebrity styling
    "明星同款", "机场穿搭", "秀场街拍",
]

# ---------------------------------------------------------------------------
# 3) BRAND_MAP -- maps every keyword to its brand (or "trend")
# ---------------------------------------------------------------------------
BRAND_MAP: dict[str, str] = {}

for brand, kws in BRAND_KEYWORDS.items():
    for kw in kws:
        BRAND_MAP[kw] = brand

for kw in TREND_KEYWORDS:
    BRAND_MAP[kw] = "trend"

# ---------------------------------------------------------------------------
# Build the flat keyword list (brands first, then trend)
# ---------------------------------------------------------------------------
ALL_KEYWORDS: list[str] = []
for kws in BRAND_KEYWORDS.values():
    ALL_KEYWORDS.extend(kws)
ALL_KEYWORDS.extend(TREND_KEYWORDS)

# ---------------------------------------------------------------------------
# Broad filter list covering all brands + trend terms
# ---------------------------------------------------------------------------
FILTER_WORDS: list[str] = [
    # Brands (English + Chinese)
    "Celine", "赛琳", "CELINE", "celine",
    "Dior", "dior", "迪奥",
    "LV", "lv", "Louis Vuitton", "路易威登",
    "Loewe", "loewe", "罗意威",
    "Chanel", "chanel", "香奈儿",
    "BV", "Bottega", "葆蝶家",
    # Trend descriptors
    "静奢", "老钱", "quiet luxury", "低调奢华",
    "极简", "高级感", "胶囊衣橱",
    "包", "穿搭", "通勤", "职场",
    "法式", "巴黎", "优雅",
    "二手", "中古", "回收",
    "明星", "机场", "秀场",
    "经典", "保值", "值得",
]

# ---------------------------------------------------------------------------
# Build command and launch
# ---------------------------------------------------------------------------
cmd = [
    PYTHON, SCRAPER,
    "--keywords", *ALL_KEYWORDS,
    "--times", "2",
    "--category", "luxury_fashion",
    "--filter", *FILTER_WORDS,
]

brand_count = len(BRAND_KEYWORDS)
brand_kw_count = sum(len(kws) for kws in BRAND_KEYWORDS.values())
trend_kw_count = len(TREND_KEYWORDS)

print(f"Launching Playwright scraper with {len(ALL_KEYWORDS)} keywords total:")
print(f"  {brand_kw_count} brand keywords across {brand_count} brands + {trend_kw_count} trend keywords")
print(f"Login cookies are saved in .pw_profile/ -- you only scan QR once.")
print(f"Data saves after EVERY keyword. Ctrl+C is safe.\n")

# Run the scraper directly via os.execvp so Ctrl+C goes straight to it
os.execvp(PYTHON, cmd)
