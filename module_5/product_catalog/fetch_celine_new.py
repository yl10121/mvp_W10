"""
Celine 新品爬虫 — 纯 requests + BeautifulSoup（不需要 Playwright）。

从 celine.com 各品类的 /new/ 页面提取:
  - 列表页: data-gtm-data (name, price, color, category, …)
  - 列表页: 产品图片 URL、详情页链接
  - （可选）详情页: 完整 description（尺寸、材质、工艺）

输出: module_5/product_catalog/new_arrivals.json

用法:
  python3 module_5/product_catalog/fetch_celine_new.py            # 仅列表页（快）
  python3 module_5/product_catalog/fetch_celine_new.py --detail   # 列表+详情页
"""

from __future__ import annotations

import json
import random
import re
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://www.celine.com"
OUTPUT_PATH = Path(__file__).resolve().parent / "new_arrivals.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

NEW_CATEGORY_PATHS = [
    "/en-us/celine-shop-women/handbags/new/",
    "/en-us/celine-shop-women/mini-bags/new/",
    "/en-us/celine-shop-women/small-leather-goods/new/",
    "/en-us/celine-shop-women/accessories/new/",
    "/en-us/celine-shop-women/jewelry/new/",
    "/en-us/celine-shop-women/shoes/new/",
    "/en-us/celine-shop-women/ready-to-wear/new/",
    "/en-us/celine-shop-men/bags/new/",
    "/en-us/celine-shop-men/small-leather-goods/new/",
    "/en-us/celine-shop-men/accessories/new/",
    "/en-us/celine-shop-men/jewelry/new/",
    "/en-us/celine-shop-men/shoes/new/",
    "/en-us/celine-shop-men/ready-to-wear/new/",
]


def _polite_delay():
    time.sleep(random.uniform(1.5, 3.5))


def _fetch(url: str) -> str | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            return resp.text
        print(f"  [WARN] {resp.status_code} for {url}")
    except requests.RequestException as e:
        print(f"  [ERR] {e}")
    return None


def _extract_listing(html: str, category_url: str) -> list[dict]:
    """从品类列表页提取产品信息。"""
    soup = BeautifulSoup(html, "html.parser")
    products: list[dict] = []
    seen_ids: set[str] = set()

    tiles = soup.find_all(attrs={"data-gtm-data": True, "data-pid": True})
    for tile in tiles:
        pid = tile.get("data-pid", "")
        if pid in seen_ids:
            continue
        seen_ids.add(pid)

        raw_gtm = urllib.parse.unquote(tile["data-gtm-data"])
        try:
            gtm = json.loads(raw_gtm)
        except json.JSONDecodeError:
            continue

        # find product detail URL (first <a> with .html href inside tile)
        detail_link = ""
        link_tag = tile.find("a", href=re.compile(r"\.html$"))
        if link_tag:
            detail_link = BASE + link_tag["href"]

        # find first image URL
        image_url = ""
        img_tag = tile.find("img", src=True)
        if img_tag:
            src = img_tag["src"]
            image_url = src.split("?")[0] if "?" in src else src

        product = {
            "product_id": gtm.get("id", pid),
            "name": gtm.get("name", ""),
            "brand": gtm.get("brand", "Celine"),
            "price": gtm.get("price"),
            "price_currency": "USD",
            "color": gtm.get("productColor", ""),
            "category": gtm.get("productMidCategory", ""),
            "sub_category": gtm.get("productSubCategory", ""),
            "top_category": gtm.get("productCategory", ""),
            "is_new": gtm.get("productFlag", "") == "NEW",
            "is_sale": gtm.get("isSale", "N") == "Y",
            "url": detail_link,
            "image_url": image_url,
            "source_category_url": BASE + category_url,
        }
        products.append(product)

    return products


def _enrich_with_detail(product: dict) -> dict:
    """从产品详情页获取 description（材质、尺寸等）。"""
    url = product.get("url")
    if not url:
        return product

    html = _fetch(url)
    if not html:
        return product

    soup = BeautifulSoup(html, "html.parser")
    ld_blocks = soup.find_all("script", type="application/ld+json")
    for block in ld_blocks:
        try:
            data = json.loads(block.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        graph = data.get("@graph", [data]) if isinstance(data, dict) else data
        if not isinstance(graph, list):
            continue

        for item in graph:
            if not isinstance(item, dict):
                continue
            if item.get("@type") != "Product":
                continue
            raw_desc = item.get("description", "")
            desc_clean = raw_desc.replace("<br>", "\n").strip()
            product["description"] = desc_clean

            offers = item.get("offers", {})
            if isinstance(offers, dict):
                product["price_currency"] = offers.get("priceCurrency", product["price_currency"])
                product["availability"] = offers.get("availability", "").replace("http://schema.org/", "")

            return product

    return product


def main() -> None:
    fetch_detail = "--detail" in sys.argv

    all_products: list[dict] = []
    seen_ids: set[str] = set()

    print(f"开始抓取 {len(NEW_CATEGORY_PATHS)} 个品类的新品列表...\n")

    for path in NEW_CATEGORY_PATHS:
        url = BASE + path
        print(f"→ {path}")
        html = _fetch(url)
        if not html:
            _polite_delay()
            continue

        products = _extract_listing(html, path)
        new_count = 0
        for p in products:
            if p["product_id"] not in seen_ids:
                seen_ids.add(p["product_id"])
                all_products.append(p)
                new_count += 1
        print(f"  提取 {len(products)} 条 (去重后新增 {new_count})")
        _polite_delay()

    print(f"\n列表阶段完成: 共 {len(all_products)} 条唯一产品")

    if fetch_detail and all_products:
        print(f"\n开始抓取详情页（共 {len(all_products)} 页）...\n")
        for i, p in enumerate(all_products):
            print(f"  [{i+1}/{len(all_products)}] {p['name'][:40]}")
            _enrich_with_detail(p)
            _polite_delay()
        print("详情抓取完成。")

    output = {
        "brand": "Celine",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "celine.com",
        "locale": "en-US",
        "total_products": len(all_products),
        "detail_fetched": fetch_detail,
        "products": all_products,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n已保存到 {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
