#!/usr/bin/env python3
"""
Quick launcher — scrapes XHS with 25 Celine-focused keywords using Playwright.
Run from module_1/:  .venv/bin/python3 run_celine_scrape.py

Chrome will open → scan the QR code with your XHS app → scraping starts.
Login cookies are saved so you only need to scan once.
"""
import subprocess
import sys
from pathlib import Path

PYTHON = str(Path(__file__).parent / ".venv" / "bin" / "python3")
SCRAPER = str(Path(__file__).parent / "xhs_scraper_pw.py")

KEYWORDS = [
    # Brand-specific
    "Celine", "Celine穿搭", "Celine包包", "Celine Triomphe", "Celine Box",
    "Celine 16手袋", "Celine Ava", "Celine西装", "Celine乐福鞋", "Celine春夏",
    "Celine大衣", "Celine墨镜", "赛琳穿搭", "赛琳包", "Celine上海",
    # Trend / aesthetic
    "静奢风穿搭", "quiet luxury", "老钱风穿搭", "极简穿搭高级感", "法式极简",
    "高奢通勤穿搭", "知识分子穿搭", "Celine牛仔裤", "Celine凉鞋", "Celine配饰",
]

FILTER_WORDS = [
    "Celine", "赛琳", "CELINE", "celine",
    "极简", "静奢", "quiet luxury", "老钱", "高奢", "包", "穿搭",
]

cmd = [
    PYTHON, SCRAPER,
    "--keywords", *KEYWORDS,
    "--times", "2",
    "--category", "luxury_fashion",
    "--filter", *FILTER_WORDS,
]

print(f"Launching Playwright scraper with {len(KEYWORDS)} keywords...")
print(f"Login cookies are saved in .pw_profile/ — you only scan QR once.")
print(f"Data saves after EVERY keyword. Ctrl+C is safe.\n")

import signal
import os
# Run the scraper directly via os.execvp so Ctrl+C goes straight to it
os.execvp(PYTHON, cmd)
