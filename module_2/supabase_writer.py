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
    "leather_goods": [
        "bag", "handbag", "tote", "clutch", "purse", "triomphe", "classique",
        "folco", "leather good", "包", "手袋", "皮具",
    ],
    "ready_to_wear": [
        "blazer", "jacket", "trouser", "trousers", "coat", "dress", "top",
        "shirt", "skirt", "sweater", "turtleneck", "tailoring", "suit",
        "外套", "西装", "大衣", "裙", "裤",
    ],
    "accessories": [
        "sunglasses", "belt", "scarf", "jewel", "chain", "bracelet", "ring",
        "眼镜", "腰带", "配饰",
    ],
    "footwear": [
        "boots", "shoes", "sneaker", "heel", "loafer", "ankle boot",
        "靴", "鞋",
    ],
}


def _infer_subcategory(label: str, hero_product: str, why_selected: str) -> str:
    """Infer product subcategory from label, hero_product, and reasoning text."""
    combined = f"{label} {hero_product or ''} {why_selected or ''}".lower()
    for subcategory, signals in _SUBCATEGORY_SIGNALS.items():
        if any(sig in combined for sig in signals):
            return subcategory
    return "general_aesthetic"


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

            # hero_product: prefer organically extracted name, fall back to LLM suggestion
            hero_product = item.get("hero_product") or item.get("hero_product_link") or ""
            hero_product_source = item.get("hero_product_source")  # "extracted_from_posts" or "llm_suggested"

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

                # ── Original 5 dimensions (kept for backward compat) ──────
                "score_freshness":    scores.get("freshness"),
                "score_brand_fit":    scores.get("brand_fit"),
                "score_category_fit": scores.get("category_fit"),
                "score_materiality":  scores.get("materiality"),
                "score_actionability": scores.get("actionability"),

                # ── Week 11 new fields ────────────────────────────────────
                "location":         item.get("location", "China"),
                "data_type":        item.get("data_type", "real"),
                "subcategory":      _infer_subcategory(label, hero_product, why_selected),
                "client_persona_match_name": item.get("matched_archetype"),
                "hero_product":        hero_product,
                "hero_product_source": hero_product_source,

                # ── Week 11 new scores ────────────────────────────────────
                "score_ca_conversational_utility": scores.get("ca_conversational_utility"),
                "score_language_specificity":      scores.get("language_specificity"),
                "score_client_persona_match":      scores.get("client_persona_match"),
                "score_novelty":                   scores.get("novelty"),
                "score_trend_velocity":            scores.get("trend_velocity"),
                "score_cross_run_persistence":     scores.get("cross_run_persistence"),

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
