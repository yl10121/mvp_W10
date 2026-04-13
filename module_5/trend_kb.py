"""
Read-only trend shortlist → payload for the LLM (small knowledge base).

Env:
  M5_TREND_KB_MODE=compact | full
    compact (default) — keep scores + summary + light signals; trim evidence / metric noise
    full              — pass through trends as loaded from Supabase (after Top-N)
"""

from __future__ import annotations

import copy
import os
from typing import Any

_MAX_EVIDENCE_ITEMS = 5
_MAX_CLUSTER_CHARS = 2500
_METRIC_KEYS = ("total_engagement", "post_count", "avg_engagement", "saves", "likes")


def _compact_one(trend: dict[str, Any]) -> dict[str, Any]:
    ev = trend.get("evidence_references")
    if isinstance(ev, list):
        ev = ev[:_MAX_EVIDENCE_ITEMS]
    else:
        ev = []

    ms = trend.get("metric_signal")
    if isinstance(ms, dict):
        ms = {k: ms[k] for k in _METRIC_KEYS if k in ms}
    else:
        ms = {}

    cs = trend.get("cluster_summary") or ""
    if isinstance(cs, str) and len(cs) > _MAX_CLUSTER_CHARS:
        cs = cs[:_MAX_CLUSTER_CHARS] + "…"

    return {
        "trend_id": trend.get("trend_id"),
        "trend_label": trend.get("trend_label"),
        "category": trend.get("category"),
        "subcategory": trend.get("subcategory"),
        "cluster_summary": cs,
        "rank": trend.get("rank"),
        "composite_score": trend.get("composite_score"),
        "confidence": trend.get("confidence"),
        "scores": trend.get("scores"),
        "hero_product": trend.get("hero_product"),
        "hero_product_source": trend.get("hero_product_source"),
        "client_persona_match_name": trend.get("client_persona_match_name"),
        "location": trend.get("location"),
        "data_type": trend.get("data_type"),
        "engagement_recency_pct": trend.get("engagement_recency_pct"),
        "low_signal_warning": trend.get("low_signal_warning"),
        "no_date_signal": trend.get("no_date_signal"),
        "disqualifying_reason": trend.get("disqualifying_reason"),
        "evidence_references": ev,
        "metric_signal": ms,
    }


def build_readonly_trend_kb(trends_data: dict[str, Any]) -> dict[str, Any]:
    """
    Build the trend block injected into the user prompt.

    query_context is copied and annotated so the model treats this batch as read-only reference.
    """
    mode = (os.environ.get("M5_TREND_KB_MODE", "compact") or "compact").strip().lower()
    if mode not in ("compact", "full"):
        mode = "compact"

    qc = dict(trends_data.get("query_context") or {})
    qc["m5_trend_kb_mode"] = mode
    qc["m5_trend_kb_role"] = "read_only_shortlist"
    qc["m5_trend_kb_note"] = (
        "Authoritative trend shortlist for this pipeline run. Read-only; not customer PII."
    )

    raw_trends = trends_data.get("trends") or []
    if mode == "full":
        trends_out = copy.deepcopy([t for t in raw_trends if isinstance(t, dict)])
    else:
        trends_out = [_compact_one(t) for t in raw_trends if isinstance(t, dict)]

    return {"query_context": qc, "trends": trends_out}
