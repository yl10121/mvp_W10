"""
module_1/supabase_reader.py
===========================
Read Module 1 brand product catalog from Supabase (same rows M1 seeds or a future API sync).

  module1_brand_products  — one row per SKU / external_id (unique per brand)

Requires SUPABASE_PASSWORD in root .env.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from supabase_client import get_conn, is_configured
except ImportError:
    def is_configured() -> bool:
        return False


def _jsonb(val: Any) -> Any:
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val
    return val


def _num(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def read_brand_products(
    brand: str | None = None,
    data_source: str | None = None,
) -> list[dict[str, Any]]:
    """
    Return catalog rows as plain dicts (JSONB decoded).

    :param brand: If set, filter `WHERE brand = %s` (e.g. \"Louis Vuitton\").
    :param data_source: Optional filter: simulated | brand_api | crawler
    """
    if not is_configured():
        raise ValueError("Supabase is not configured (SUPABASE_PASSWORD missing).")

    conn = get_conn()
    cur = conn.cursor()

    clauses: list[str] = []
    params: list[Any] = []
    if brand:
        clauses.append("brand = %s")
        params.append(brand)
    if data_source:
        clauses.append("data_source = %s")
        params.append(data_source)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    cur.execute(
        "SELECT id, run_id, brand, external_id, name, category, description, "
        "price_amount, currency, product_url, image_urls, attributes, "
        "data_source, raw_payload, created_at, updated_at "
        "FROM module1_brand_products"
        + where
        + " ORDER BY brand, external_id",
        params,
    )
    cols = [d[0] for d in cur.description]
    rows_out: list[dict[str, Any]] = []
    for r in cur.fetchall():
        row = dict(zip(cols, r))
        row["image_urls"] = _jsonb(row.get("image_urls")) or []
        row["attributes"] = _jsonb(row.get("attributes")) or {}
        row["raw_payload"] = _jsonb(row.get("raw_payload")) or {}
        row["price_amount"] = _num(row.get("price_amount"))
        for ts_key in ("created_at", "updated_at"):
            v = row.get(ts_key)
            if isinstance(v, datetime):
                row[ts_key] = v.isoformat()
        rows_out.append(row)
    conn.close()
    return rows_out
