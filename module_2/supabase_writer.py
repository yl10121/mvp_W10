"""
supabase_writer.py — Module 2 Supabase persistence helpers.

Writes trend shortlists and run logs to module2_* tables.
Uses ON CONFLICT (run_id, trend_id) DO UPDATE so re-runs update existing rows.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from supabase_client import get_conn, is_configured, insert_row


# ── Subcategory inference ──────────────────────────────────────────────────────

_SUBCATEGORY_SIGNALS = {
    "engagement_rings": [
        "engagement", "solitaire", "propose", "proposal", "diamond ring", "求婚戒",
        "求婚", "订婚", "tiffany setting", "soleste", "tiffany true",
    ],
    "rings": [
        "ring", "band", "戒指", "指环", "t1", "atlas", "硬汉", "lock ring",
    ],
    "bracelets": [
        "bracelet", "bangle", "cuff", "手链", "手镯", "hardwear", "lock bracelet",
        "t wire", "硬件系列",
    ],
    "necklaces": [
        "necklace", "pendant", "chain", "项链", "吊坠", "return to tiffany",
        "heart tag", "keys", "smile", "victoria", "蒂芙尼项链",
    ],
    "earrings": [
        "earring", "stud", "hoop", "drop earring", "耳环", "耳坠", "耳钉",
    ],
}


def _infer_subcategory(label: str, hero_product: str, why_selected: str) -> str:
    """Infer product subcategory from label, hero_product, and reasoning text."""
    combined = f"{label} {hero_product or ''} {why_selected or ''}".lower()
    for subcategory, signals in _SUBCATEGORY_SIGNALS.items():
        if any(sig in combined for sig in signals):
            return subcategory
    return "general_jewelry"


# ── Upsert helper ──────────────────────────────────────────────────────────────

def _upsert_shortlist_row(conn, row: dict) -> None:
    """
    Upsert a single shortlist row using ON CONFLICT (run_id, trend_id) DO UPDATE.
    Falls back to ON CONFLICT DO NOTHING if the unique constraint doesn't exist yet.
    All dict/list values are serialised to JSON for JSONB columns.
    """
    clean = {
        k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
        for k, v in row.items()
    }
    cols = ", ".join(clean.keys())
    placeholders = ", ".join(["%s"] * len(clean))
    updates = ", ".join(
        f"{k}=EXCLUDED.{k}" for k in clean if k not in ("run_id", "trend_id")
    )
    sql = (
        f"INSERT INTO module2_trend_shortlist ({cols}) VALUES ({placeholders}) "
        f"ON CONFLICT (run_id, trend_id) DO UPDATE SET {updates};"
    )
    try:
        with conn.cursor() as cur:
            cur.execute(sql, list(clean.values()))
        conn.commit()
    except Exception:
        conn.rollback()
        # Fallback if unique constraint doesn't exist yet
        fallback_sql = (
            f"INSERT INTO module2_trend_shortlist ({cols}) VALUES ({placeholders}) "
            f"ON CONFLICT DO NOTHING;"
        )
        try:
            with conn.cursor() as cur:
                cur.execute(fallback_sql, list(clean.values()))
            conn.commit()
        except Exception as e2:
            conn.rollback()
            print(f"  [DB WARN] shortlist upsert failed: {e2}")


# ── Public write functions ─────────────────────────────────────────────────────

def write_shortlist(run_id: str, shortlist_output: dict) -> None:
    """
    Upsert each shortlisted trend into module2_trend_shortlist.
    Includes all Week 11 dimensions and metadata fields.
    Uses ON CONFLICT (run_id, trend_id) DO UPDATE — safe to re-run.
    """
    if not is_configured():
        return
    conn = get_conn()
    try:
        upserted = 0
        for item in shortlist_output.get("shortlist", []):
            scores = item.get("scores") or {}
            metric = item.get("metric_signal") or {}
            why_selected = item.get("why_selected") or ""
            label = item.get("label") or ""

            # hero_product comes only from organically extracted XHS product mentions (Step 1.5)
            hero_product = item.get("hero_product") or ""
            hero_product_source = item.get("hero_product_source")  # "extracted_from_posts" or None

            row = {
                # ── Core identity ─────────────────────────────────────────
                "run_id":          run_id,
                "module1_run_id":  shortlist_output.get("module1_run_id"),
                "brand":           shortlist_output.get("brand"),
                "trend_id":        item.get("trend_id"),
                "rank":            item.get("rank"),
                "label":           label,
                "category":        item.get("category"),
                "composite_score": item.get("composite_score"),
                "confidence":      item.get("confidence"),
                "why_selected":    why_selected,
                "evidence_references": item.get("evidence_references", []),
                "metric_signal":   metric,

                # ── Product signal (extracted from XHS posts only) ────────
                "location":         item.get("location", "China"),
                "data_type":        item.get("data_type", "real"),
                "subcategory":      _infer_subcategory(label, hero_product, why_selected),
                "hero_product":        hero_product,
                "hero_product_source": hero_product_source,

                # ── 8-dimension scores ────────────────────────────────────
                "score_brand_engagement_depth":        scores.get("brand_engagement_depth"),
                "score_client_touchpoint_specificity": scores.get("client_touchpoint_specificity"),
                "score_vocabulary_transfer_potential": scores.get("vocabulary_transfer_potential"),
                "score_intelligence_value":            scores.get("intelligence_value"),
                "score_client_segment_clarity":        scores.get("client_segment_clarity"),
                "score_occasion_purchase_trigger":     scores.get("occasion_purchase_trigger"),
                "score_trend_velocity":                scores.get("trend_velocity"),
                "score_evidence_credibility":          scores.get("evidence_credibility"),

                # ── Composite scores ──────────────────────────────────────
                "raw_composite_score":          item.get("raw_composite_score"),
                "confidence_weighted_composite": item.get("confidence_weighted_composite"),
                "confidence_weight":            item.get("confidence_weight"),
                "velocity_method":              item.get("velocity_method"),

                # ── Signal flags ──────────────────────────────────────────
                "celebrity_signal":   bool(item.get("celebrity_signal", False)),
                "occasion_signal":    bool(item.get("occasion_signal", False)),
                "competitor_signal":  bool(item.get("competitor_signal", False)),
                "competitor_mentions": item.get("competitor_mentions", []),
                "best_evidence_quote": item.get("best_evidence_quote", ""),

                # ── Signal metadata ───────────────────────────────────────
                "engagement_recency_pct": metric.get("engagement_recency_pct"),
                "low_signal_warning":    bool(item.get("low_signal_warning")),
                "no_date_signal":        bool(item.get("no_date_signal")),
                "disqualifying_reason":  item.get("disqualifying_reason"),
            }

            # Remove None values to avoid overwriting existing data with nulls
            row = {k: v for k, v in row.items() if v is not None}

            _upsert_shortlist_row(conn, row)
            upserted += 1

        if upserted:
            print(f"[Supabase] Upserted {upserted} shortlist row(s) into module2_trend_shortlist.")
    finally:
        conn.close()


def write_run_log(
    run_id: str,
    module1_run_id: str,
    total_input: int,
    prefilter_rejected: int,
    passed_to_llm: int,
    shortlisted: int,
    generated_at: str,
) -> None:
    """Insert a run log row into module2_run_logs."""
    if not is_configured():
        return
    conn = get_conn()
    try:
        insert_row(conn, "module2_run_logs", {
            "run_id":             run_id,
            "module1_run_id":     module1_run_id,
            "total_input":        total_input,
            "prefilter_rejected": prefilter_rejected,
            "passed_to_llm":      passed_to_llm,
            "shortlisted":        shortlisted,
            "noise_reduction_pct": round(
                (total_input - shortlisted) / max(total_input, 1) * 100, 1
            ),
            "generated_at": generated_at,
        })
        print("[Supabase] Run log inserted.")
    finally:
        conn.close()
