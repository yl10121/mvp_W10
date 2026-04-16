#!/usr/bin/env python3
"""
Seed Supabase module1_brand_products with static, web-plausible rows.

Same schema and table as a future brand API sync — swap data_source to
brand_api when ingesting live payloads; readers stay unchanged.

Prerequisites:
  1. Run db/migrations/module1_brand_products.sql in the Supabase SQL editor.
  2. SUPABASE_PASSWORD (and related vars) in root .env.

Usage (from repo root):
  .venv/bin/python3 module_1/seed_brand_products.py

From module_1:
  ../.venv/bin/python3 seed_brand_products.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from supabase_client import get_conn, is_configured  # noqa: E402

from module_1.supabase_writer import upsert_brand_products  # noqa: E402


def _apply_migration_sql() -> None:
    """Create module1_brand_products if missing (idempotent)."""
    path = REPO / "db" / "migrations" / "module1_brand_products.sql"
    text = path.read_text(encoding="utf-8")
    lines = []
    for line in text.splitlines():
        if line.strip().startswith("--"):
            continue
        lines.append(line)
    blob = "\n".join(lines)
    chunks = [c.strip() for c in blob.split(";") if c.strip()]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for ch in chunks:
                cur.execute(ch + ";")
        conn.commit()
    finally:
        conn.close()

# Static snapshot — names/URLs/points inspired by public brand sites (not scraped).
RUN_ID = "m1_simulated_catalog_v1"

SIMULATED_PRODUCTS: list[dict] = [
    {
        "brand": "Louis Vuitton",
        "external_id": "LV-N41358",
        "name": "Neverfull MM",
        "category": "Handbags",
        "description": "Iconic tote in Monogram canvas with leather trim and side laces.",
        "price_amount": 1750.00,
        "currency": "EUR",
        "product_url": "https://en.louisvuitton.com/eng-nl/products/neverfull-mm-monogram-n41358",
        "image_urls": [],
        "attributes": {
            "line": "Monogram",
            "material": "Coated canvas",
            "size": "MM",
        },
        "data_source": "simulated",
        "raw_payload": {
            "style": "N41358",
            "collection": "Neverfull",
        },
    },
    {
        "brand": "Louis Vuitton",
        "external_id": "LV-M41112",
        "name": "Speedy Bandoulière 25",
        "category": "Handbags",
        "description": "Structured city bag with detachable strap and rolled leather handles.",
        "price_amount": 1690.00,
        "currency": "EUR",
        "product_url": "https://en.louisvuitton.com/eng-nl/products/speedy-bandouliere-25-monogram",
        "image_urls": [],
        "attributes": {"line": "Monogram", "size": "25"},
        "data_source": "simulated",
        "raw_payload": {"style": "M41112"},
    },
    {
        "brand": "Louis Vuitton",
        "external_id": "LV-M45847",
        "name": "OnThego MM",
        "category": "Handbags",
        "description": "Large Monogram tote with short top handles and long shoulder straps.",
        "price_amount": 2350.00,
        "currency": "EUR",
        "product_url": "https://en.louisvuitton.com/eng-nl/products/onthego-mm-monogram",
        "image_urls": [],
        "attributes": {"line": "Monogram", "size": "MM"},
        "data_source": "simulated",
        "raw_payload": {"style": "M45847"},
    },
    {
        "brand": "Louis Vuitton",
        "external_id": "LV-M40780",
        "name": "Pochette Métis",
        "category": "Handbags",
        "description": "Compact Monogram satchel with top handle and removable strap.",
        "price_amount": 2150.00,
        "currency": "EUR",
        "product_url": "https://en.louisvuitton.com/eng-nl/products/pochette-metis-monogram",
        "image_urls": [],
        "attributes": {"line": "Monogram"},
        "data_source": "simulated",
        "raw_payload": {"style": "M40780"},
    },
    {
        "brand": "Louis Vuitton",
        "external_id": "LV-M94517",
        "name": "Capucines BB",
        "category": "Handbags",
        "description": "Full-grain Taurillon leather top-handle bag with LV signature clasp.",
        "price_amount": 4700.00,
        "currency": "EUR",
        "product_url": "https://en.louisvuitton.com/eng-nl/products/capucines-bb-taurillon",
        "image_urls": [],
        "attributes": {"line": "Capucines", "size": "BB"},
        "data_source": "simulated",
        "raw_payload": {"style": "M94517"},
    },
    {
        "brand": "Louis Vuitton",
        "external_id": "LV-M44875",
        "name": "Multi Pochette Accessoires",
        "category": "Handbags",
        "description": "Three removable pouches on a removable gold-tone chain and strap.",
        "price_amount": 1890.00,
        "currency": "EUR",
        "product_url": "https://en.louisvuitton.com/eng-nl/products/multi-pochette-accessoires-monogram",
        "image_urls": [],
        "attributes": {"line": "Monogram"},
        "data_source": "simulated",
        "raw_payload": {"style": "M44875"},
    },
    {
        "brand": "Celine",
        "external_id": "CE-191242BNZ",
        "name": "Teen Triomphe Bag in shiny calfskin",
        "category": "Handbags",
        "description": "Triomphe closure; adjustable leather strap; made in Italy.",
        "price_amount": 3200.00,
        "currency": "EUR",
        "product_url": "https://www.celine.com/en-int/celine-women/handbags/triomphe/",
        "image_urls": [],
        "attributes": {"line": "Triomphe", "leather": "Shiny calfskin"},
        "data_source": "simulated",
        "raw_payload": {"family": "Triomphe", "region": "INT"},
    },
    {
        "brand": "Celine",
        "external_id": "CE-114493BF4",
        "name": "Ava Bag in Triomphe canvas and calfskin",
        "category": "Handbags",
        "description": "Shoulder bag with Triomphe canvas and tan leather trim.",
        "price_amount": 1450.00,
        "currency": "EUR",
        "product_url": "https://www.celine.com/en-int/celine-women/handbags/ava/",
        "image_urls": [],
        "attributes": {"line": "Ava", "material": "Canvas and calfskin"},
        "data_source": "simulated",
        "raw_payload": {"family": "Ava"},
    },
]


def main() -> None:
    if not is_configured():
        print("SUPABASE_PASSWORD not set — add credentials to .env and retry.")
        sys.exit(1)
    print("Ensuring table module1_brand_products exists…")
    try:
        _apply_migration_sql()
    except Exception as e:
        print(
            f"Migration apply failed ({e}).\n"
            "Run db/migrations/module1_brand_products.sql manually in the Supabase SQL editor, "
            "then re-run this script."
        )
        sys.exit(1)
    n = upsert_brand_products(RUN_ID, SIMULATED_PRODUCTS)
    print(f"Done. Upserted {n} product row(s) (run_id={RUN_ID}).")
    print("Read back:  from module_1.supabase_reader import read_brand_products")


if __name__ == "__main__":
    main()
