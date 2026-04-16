"""
module_1/supabase_writer.py
============================
Writes Module 1 outputs to Supabase after each run.
Called automatically by xhs_trend_builder.py and xhs_scraper_live.py
when SUPABASE_PASSWORD is set in .env.

Tables written:
  module1_xhs_posts        — one row per scraped/processed post
  module1_trend_objects    — one row per trend object
  module1_run_logs         — one row per pipeline run
  module1_brand_products   — brand catalog (simulated or API); upsert by (brand, external_id)
"""

from __future__ import annotations
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from supabase_client import get_conn, insert_row, insert_rows, is_configured
except ImportError:
    def is_configured():
        return False


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Posts ─────────────────────────────────────────────────────────
def write_posts(run_id: str, posts: list[dict[str, Any]]) -> int:
    """Write processed xhs_posts list to module1_xhs_posts."""
    if not is_configured():
        return 0
    conn = get_conn()
    rows = []
    for p in posts:
        rows.append({
            "run_id":                  run_id,
            "post_id":                 p.get("post_id", ""),
            "keyword":                 p.get("keyword", ""),
            "category":                p.get("category", ""),
            "date":                    p.get("date", ""),
            "title":                   p.get("title", ""),
            "caption":                 p.get("caption", ""),
            "hashtags":                p.get("hashtags", []),
            "likes":                   p.get("likes", 0),
            "comment_count":           p.get("comment_count", p.get("comments", 0)),
            "saves":                   p.get("saves", 0),
            "creator":                 p.get("creator", ""),
            "post_link":               p.get("post_link", ""),
            "cover_url":               p.get("cover_url", ""),
            "all_image_urls":          p.get("all_image_urls", []),
            "is_video":                p.get("is_video", False),
            "video_url":               p.get("video_url", ""),
            "image_caption":           p.get("image_caption", ""),
            "comments_scraped":        p.get("comments_scraped", []),
            "comments_count_scraped":  p.get("comments_count_scraped", 0),
        })
    inserted = insert_rows(conn, "module1_xhs_posts", rows)
    conn.close()
    print(f"  [DB] module1_xhs_posts ← {inserted}/{len(rows)} rows")
    return inserted


# ── Trend objects ─────────────────────────────────────────────────
def write_trend_objects(run_id: str,
                        trend_objects: list[dict[str, Any]]) -> int:
    """Write trend objects list to module1_trend_objects."""
    if not is_configured():
        return 0
    conn = get_conn()
    rows = []
    for t in trend_objects:
        rows.append({
            "run_id":          run_id,
            "trend_id":        t.get("trend_id", ""),
            "label":           t.get("label", ""),
            "category":        t.get("category", ""),
            "summary":         t.get("summary", ""),
            "ai_reasoning":    t.get("ai_reasoning", ""),
            "confidence":      t.get("confidence", ""),
            "labeling_source": t.get("labeling_source", ""),
            "evidence":        t.get("evidence", {}),
            "metrics":         t.get("metrics", {}),
            "visual_assets":   t.get("visual_assets", {}),
            "comment_signals": t.get("comment_signals", {}),
        })
    inserted = insert_rows(conn, "module1_trend_objects", rows)
    conn.close()
    print(f"  [DB] module1_trend_objects ← {inserted}/{len(rows)} rows")
    return inserted


# ── Run log ───────────────────────────────────────────────────────
def write_run_log(run_log: dict[str, Any]) -> int | None:
    """Write a single run log entry to module1_run_logs."""
    if not is_configured():
        return None
    conn = get_conn()
    row = {
        "run_id":            run_log.get("run_id", ""),
        "brand":             run_log.get("brand", ""),
        "category":          run_log.get("category", ""),
        "time_window":       run_log.get("time_window", {}),
        "records_loaded":    run_log.get("retrieval", {}).get("records_loaded", 0),
        "records_retrieved": run_log.get("retrieval", {}).get("records_retrieved", 0),
        "trend_count":       len(run_log.get("trend_objects", [])),
        "llm_enabled":       run_log.get("decision_logic", {}).get("llm_enabled", False),
        "llm_model":         run_log.get("decision_logic", {}).get("llm_model", ""),
        "llm_errors":        run_log.get("decision_logic", {}).get("llm_errors", []),
        "keywords_scraped":  run_log.get("keywords_scraped", []),
    }
    new_id = insert_row(conn, "module1_run_logs", row)
    conn.close()
    if new_id:
        print(f"  [DB] module1_run_logs ← run_id={row['run_id']} (id={new_id})")
    return new_id


def upsert_brand_products(run_id: str, products: list[dict[str, Any]]) -> int:
    """
    Upsert brand catalog rows into module1_brand_products.
    Conflict key: (brand, external_id). Same call shape for simulated or API rows.

    Each product dict may include:
      brand, external_id, name, category, description, price_amount, currency,
      product_url, image_urls, attributes, data_source, raw_payload
    """
    import json as _json

    if not is_configured():
        return 0
    if not products:
        return 0

    conn = get_conn()
    sql = """
    INSERT INTO module1_brand_products (
        run_id, brand, external_id, name, category, description,
        price_amount, currency, product_url, image_urls, attributes,
        data_source, raw_payload
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s::jsonb
    )
    ON CONFLICT (brand, external_id) DO UPDATE SET
        run_id = EXCLUDED.run_id,
        name = EXCLUDED.name,
        category = EXCLUDED.category,
        description = EXCLUDED.description,
        price_amount = EXCLUDED.price_amount,
        currency = EXCLUDED.currency,
        product_url = EXCLUDED.product_url,
        image_urls = EXCLUDED.image_urls,
        attributes = EXCLUDED.attributes,
        data_source = EXCLUDED.data_source,
        raw_payload = EXCLUDED.raw_payload,
        updated_at = NOW()
    """
    ok = 0
    try:
        with conn.cursor() as cur:
            for p in products:
                img = p.get("image_urls", [])
                att = p.get("attributes", {})
                raw = p.get("raw_payload", {})
                vals = (
                    run_id,
                    p.get("brand", ""),
                    p.get("external_id", ""),
                    p.get("name", ""),
                    p.get("category"),
                    p.get("description"),
                    p.get("price_amount"),
                    p.get("currency") or "EUR",
                    p.get("product_url", ""),
                    _json.dumps(img, ensure_ascii=False),
                    _json.dumps(att, ensure_ascii=False),
                    p.get("data_source") or "simulated",
                    _json.dumps(raw, ensure_ascii=False),
                )
                cur.execute(sql, vals)
                ok += 1
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"  [DB WARN] upsert_brand_products failed: {e}")
        ok = 0
    finally:
        conn.close()
    print(f"  [DB] module1_brand_products ← {ok}/{len(products)} upserts")
    return ok
