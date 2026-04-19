#!/usr/bin/env python3
"""
Tiffany & Co. XHS Scraper — scrapes jewelry trends relevant to Tiffany CAs.
Covers Tiffany-specific content, competitor brands, and general jewelry trends.
Run from module_1/: .venv/bin/python3 run_tiffany_scrape.py
Chrome will open -> scan QR code with XHS app -> scraping starts.
"""

import os
from pathlib import Path

PYTHON = str(Path(__file__).parent / ".venv" / "bin" / "python3")
SCRAPER = str(Path(__file__).parent / "xhs_scraper_pw.py")

BRAND_KEYWORDS = {
    "Tiffany": [
        "Tiffany", "蒂芙尼", "Tiffany&Co",
        "Tiffany T系列", "Tiffany HardWear", "Tiffany Lock",
        "Tiffany Setting", "六爪钻戒", "蒂芙尼订婚戒指",
        "蒂芙尼项链", "蒂芙尼手链", "蒂芙尼戒指",
        "Tiffany蓝", "蒂芙尼开箱",
    ],
    "Cartier": [
        "Cartier", "卡地亚", "Cartier Love", "卡地亚love手镯",
    ],
    "Van Cleef": [
        "Van Cleef", "梵克雅宝", "四叶草项链",
    ],
    "Bvlgari": [
        "Bvlgari", "宝格丽", "宝格丽蛇形",
    ],
    "Harry Winston": [
        "Harry Winston", "海瑞温斯顿",
    ],
}

TREND_KEYWORDS = [
    "珠宝穿搭", "轻奢珠宝", "珠宝叠戴", "叠戴手链", "叠戴项链",
    "求婚戒指推荐", "婚戒选择", "情侣对戒", "纪念日礼物",
    "明星珠宝同款", "珠宝开箱", "保值珠宝", "高级珠宝入门",
    "珠宝品牌对比", "珠宝送礼攻略", "婚礼珠宝", "订婚戒指",
    "18k金首饰", "铂金首饰", "珠宝保养", "中古珠宝",
]

BRAND_MAP = {}
for brand, kws in BRAND_KEYWORDS.items():
    for kw in kws:
        BRAND_MAP[kw] = brand
for kw in TREND_KEYWORDS:
    BRAND_MAP[kw] = "trend"

ALL_KEYWORDS = []
for kws in BRAND_KEYWORDS.values():
    ALL_KEYWORDS.extend(kws)
ALL_KEYWORDS.extend(TREND_KEYWORDS)

FILTER_WORDS = [
    "Tiffany", "蒂芙尼", "tiffany",
    "Cartier", "卡地亚", "Van Cleef", "梵克雅宝",
    "Bvlgari", "宝格丽", "Harry Winston", "海瑞温斯顿",
    "珠宝", "戒指", "项链", "手链", "手镯",
    "钻石", "黄金", "铂金", "18k",
    "求婚", "婚戒", "订婚", "纪念",
    "明星", "开箱", "保值", "叠戴",
]

cmd = [
    PYTHON, SCRAPER,
    "--keywords", *ALL_KEYWORDS,
    "--times", "3",
    "--category", "luxury_jewelry",
    "--filter", *FILTER_WORDS,
]

print(f"Launching Tiffany jewelry scraper with {len(ALL_KEYWORDS)} keywords")
print(f"Login cookies saved in .pw_profile/ — scan QR once")
print(f"Data saves after EVERY keyword. Ctrl+C is safe.\n")

os.execvp(PYTHON, cmd)
