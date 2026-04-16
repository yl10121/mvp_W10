"""
module_5/supabase_reader.py
Read Module 5 inputs from Supabase — the same tables Module 2 and Module 4 write to.

  - module2_trend_shortlist   ← Module 2 shortlist output (full extended schema)
  - module4_client_memories   ← Module 4 structured memory output

Optional env (pin a specific pipeline run):
  M5_MODULE2_RUN_ID  — module2_trend_shortlist.run_id (default: latest by created_at)
  M5_MODULE4_RUN_ID  — module4_client_memories.run_id (default: latest by generated_at)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from supabase_client import get_conn, is_configured


def _jsonb(val: Any) -> Any:
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val
    return val


def _ts(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.isoformat()
    return str(val)


def _float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


_M2_SELECT = """
SELECT trend_id, rank, label, category, composite_score,
       score_freshness, score_brand_fit, score_category_fit,
       score_materiality, score_actionability,
       score_ca_conversational_utility, score_language_specificity,
       score_client_persona_match, score_novelty, score_trend_velocity,
       score_cross_run_persistence,
       confidence, why_selected, evidence_references, metric_signal,
       brand, module1_run_id,
       location, data_type, subcategory, client_persona_match_name, hero_product,
       hero_product_source,
       engagement_recency_pct, low_signal_warning, no_date_signal, disqualifying_reason
FROM module2_trend_shortlist
WHERE run_id = %s ORDER BY rank NULLS LAST, trend_id
"""


def read_trend_shortlist(run_id: str | None = None) -> dict[str, Any]:
    """
    Read rows from module2_trend_shortlist (written by Module 2).
    If run_id is None, uses M5_MODULE2_RUN_ID or the most recent run in the table.
    Returns: {"query_context": {...}, "trends": [...]} for M5.
    """
    run_id = (run_id or os.environ.get("M5_MODULE2_RUN_ID", "").strip()) or None

    conn = get_conn()
    cur = conn.cursor()

    if run_id is None:
        cur.execute(
            "SELECT run_id FROM module2_trend_shortlist "
            "ORDER BY created_at DESC LIMIT 1"
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            raise ValueError("No trend shortlist rows found in module2_trend_shortlist.")
        run_id = row[0]

    cur.execute(_M2_SELECT, (run_id,))
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    conn.close()

    if not rows:
        raise ValueError(f"No trends found for run_id={run_id} in module2_trend_shortlist.")

    meta = rows[0]
    query_context = {
        "brand": meta.get("brand"),
        "module1_run_id": meta.get("module1_run_id"),
        "module2_run_id": run_id,
        "source": "supabase:module2_trend_shortlist",
    }

    trends = []
    for r in rows:
        trends.append({
            "trend_id": r["trend_id"],
            "trend_label": r["label"],
            "category": r["category"] or "",
            "cluster_summary": r["why_selected"] or "",
            "composite_score": _float(r.get("composite_score")),
            "scores": {
                "freshness": _float(r.get("score_freshness")),
                "brand_fit": _float(r.get("score_brand_fit")),
                "category_fit": _float(r.get("score_category_fit")),
                "materiality": _float(r.get("score_materiality")),
                "actionability": _float(r.get("score_actionability")),
                "ca_conversational_utility": _float(r.get("score_ca_conversational_utility")),
                "language_specificity": _float(r.get("score_language_specificity")),
                "client_persona_match": _float(r.get("score_client_persona_match")),
                "novelty": _float(r.get("score_novelty")),
                "trend_velocity": _float(r.get("score_trend_velocity")),
                "cross_run_persistence": _float(r.get("score_cross_run_persistence")),
            },
            "confidence": r["confidence"],
            "evidence_references": _jsonb(r.get("evidence_references", [])),
            "metric_signal": _jsonb(r.get("metric_signal", {})),
            "rank": r["rank"],
            "source_format": "module2_trend_shortlist",
            "location": r.get("location"),
            "data_type": r.get("data_type"),
            "subcategory": r.get("subcategory"),
            "client_persona_match_name": r.get("client_persona_match_name"),
            "hero_product": r.get("hero_product"),
            "hero_product_source": r.get("hero_product_source"),
            "engagement_recency_pct": _float(r.get("engagement_recency_pct")),
            "low_signal_warning": r.get("low_signal_warning"),
            "no_date_signal": r.get("no_date_signal"),
            "disqualifying_reason": r.get("disqualifying_reason"),
        })

    return {"query_context": query_context, "trends": trends}


def _row_to_m5_client(r: dict[str, Any]) -> dict[str, Any]:
    """
    Map a module4_client_memories row to one M5 'client' object.
    Uses client_id / display_name / persona_tag / vip_tier when present (PRD columns).
    """
    rid = r.get("run_id", "unknown")
    db_id = r.get("id")
    cid = (r.get("client_id") or "").strip()
    if not cid:
        cid = f"m4_{rid}_{db_id}"
    display = (r.get("display_name") or "").strip()
    if not display:
        display = "Client (Module 4)"
    ptag = (r.get("persona_tag") or "").strip()
    if not ptag:
        ptag = "module4_structured_memory"
    vip = (r.get("vip_tier") or "").strip()
    if not vip:
        vip = "N/A"

    return {
        "memory_row_id": db_id,
        "client_id": cid,
        "name": display,
        "persona_tag": ptag,
        "vip_tier": vip,
        "source_table": "module4_client_memories",
        "module4_run_id": rid,
        "module4_memory_row_id": db_id,
        "generated_at": _ts(r.get("generated_at")),
        "model_used": r.get("model_used"),
        "missing_fields_count": r.get("missing_fields_count"),
        "raw_voice_note": r.get("raw_voice_note") or "",
        "summary": r.get("summary") or "",
        "life_event": _jsonb(r.get("life_event", {})),
        "timeline": _jsonb(r.get("timeline", {})),
        "aesthetic_preference": _jsonb(r.get("aesthetic_preference", {})),
        "size_height": _jsonb(r.get("size_height", {})),
        "budget": _jsonb(r.get("budget", {})),
        "mood": _jsonb(r.get("mood", {})),
        "trend_signals": _jsonb(r.get("trend_signals", {})),
        "next_step_intent": _jsonb(r.get("next_step_intent", {})),
        "confidence_summary": _jsonb(r.get("confidence_summary", {})),
    }


def _resolve_m4_run_id(cur, run_id: str | None) -> str:
    run_id = (run_id or os.environ.get("M5_MODULE4_RUN_ID", "").strip()) or None
    if run_id is None:
        cur.execute(
            "SELECT run_id FROM module4_client_memories "
            "ORDER BY generated_at DESC LIMIT 1"
        )
        row = cur.fetchone()
        if not row:
            raise ValueError("No rows found in module4_client_memories.")
        run_id = row[0]
    return run_id


def read_m4_client_summaries(run_id: str | None = None) -> tuple[str, list[dict[str, Any]]]:
    """
    Lightweight rows for CA picker: no large JSONB blobs in the bundle.
    Returns (resolved_run_id, [{memory_row_id, client_id, name, persona_tag, vip_tier}, ...]).
    Full memory is loaded per client at generation time (see fetch_m4_client_full_by_pk).
    """
    conn = get_conn()
    cur = conn.cursor()
    rid = _resolve_m4_run_id(cur, run_id)
    cur.execute(
        "SELECT id, run_id, client_id, display_name, persona_tag, vip_tier "
        "FROM module4_client_memories WHERE run_id = %s ORDER BY id",
        (rid,),
    )
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    conn.close()

    out: list[dict[str, Any]] = []
    for r in rows:
        db_id = r["id"]
        rid_row = r["run_id"]
        cid = (r.get("client_id") or "").strip()
        if not cid:
            cid = f"m4_{rid_row}_{db_id}"
        name = (r.get("display_name") or "").strip() or "Client (Module 4)"
        ptag = (r.get("persona_tag") or "").strip() or "module4_structured_memory"
        vip = (r.get("vip_tier") or "").strip() or "N/A"
        out.append({
            "memory_row_id": db_id,
            "client_id": cid,
            "name": name,
            "persona_tag": ptag,
            "vip_tier": vip,
        })
    return rid, out


def fetch_m4_client_full_by_pk(m4_run_id: str, memory_row_id: int) -> dict[str, Any]:
    """Load one full client memory row for LLM context (tool-style on-demand fetch)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, run_id, client_id, display_name, persona_tag, vip_tier, "
        "       raw_voice_note, summary, life_event, timeline, "
        "       aesthetic_preference, size_height, budget, mood, trend_signals, "
        "       next_step_intent, model_used, confidence_summary, missing_fields_count, "
        "       generated_at "
        "FROM module4_client_memories WHERE run_id = %s AND id = %s",
        (m4_run_id, memory_row_id),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        raise ValueError(
            f"No module4_client_memories row for run_id={m4_run_id!r} id={memory_row_id}"
        )
    cols = [d[0] for d in cur.description]
    return _row_to_m5_client(dict(zip(cols, row)))


def read_module4_client_memories(run_id: str | None = None) -> dict[str, Any]:
    """
    Read rows from module4_client_memories (written by Module 4).
    If run_id is None, uses M5_MODULE4_RUN_ID or the latest run_id by generated_at.
    Returns: {"clients": [ {...}, ... ]} — each item is the real M4 memory shape for the LLM.
    """
    run_id = (run_id or os.environ.get("M5_MODULE4_RUN_ID", "").strip()) or None

    conn = get_conn()
    cur = conn.cursor()

    if run_id is None:
        cur.execute(
            "SELECT run_id FROM module4_client_memories "
            "ORDER BY generated_at DESC LIMIT 1"
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            raise ValueError("No rows found in module4_client_memories.")
        run_id = row[0]

    cur.execute(
        "SELECT id, run_id, client_id, display_name, persona_tag, vip_tier, "
        "       raw_voice_note, summary, life_event, timeline, "
        "       aesthetic_preference, size_height, budget, mood, trend_signals, "
        "       next_step_intent, model_used, confidence_summary, missing_fields_count, "
        "       generated_at "
        "FROM module4_client_memories WHERE run_id = %s ORDER BY id",
        (run_id,),
    )
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    conn.close()

    if not rows:
        raise ValueError(f"No module4_client_memories rows for run_id={run_id}.")

    clients = [_row_to_m5_client(r) for r in rows]
    return {"clients": clients}


if __name__ == "__main__":
    if not is_configured():
        print("Supabase not configured (SUPABASE_PASSWORD missing).")
        sys.exit(1)
    import json as _json
    print("── module2_trend_shortlist ──")
    try:
        ts = read_trend_shortlist()
        print(f"  trends: {len(ts['trends'])}  run={ts['query_context'].get('module2_run_id')}")
        print(_json.dumps(ts, ensure_ascii=False, indent=2)[:1200])
    except Exception as e:
        print(f"  ERROR: {e}")
    print("\n── module4_client_memories ──")
    try:
        cp = read_module4_client_memories()
        print(f"  clients: {len(cp['clients'])}")
        for c in cp["clients"]:
            print(f"  - {c['client_id']}  summary[:60]={str(c.get('summary',''))[:60]}")
    except Exception as e:
        print(f"  ERROR: {e}")
