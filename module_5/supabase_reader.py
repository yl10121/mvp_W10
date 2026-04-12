"""
module_5/supabase_reader.py
Read Module 5 inputs from Supabase — the same tables Module 2 and Module 4 write to.

  - module2_trend_shortlist   ← Module 2 shortlist output
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


# ── Module 2: trend shortlist ─────────────────────────────────────

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

    cur.execute(
        "SELECT trend_id, rank, label, category, composite_score, "
        "       score_freshness, score_brand_fit, score_category_fit, "
        "       score_materiality, score_actionability, "
        "       confidence, why_selected, evidence_references, metric_signal, "
        "       brand, module1_run_id "
        "FROM module2_trend_shortlist "
        "WHERE run_id = %s ORDER BY rank NULLS LAST, trend_id",
        (run_id,),
    )
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
            "composite_score": float(r["composite_score"]) if r["composite_score"] is not None else None,
            "scores": {
                "freshness": float(r["score_freshness"]) if r["score_freshness"] is not None else None,
                "brand_fit": float(r["score_brand_fit"]) if r["score_brand_fit"] is not None else None,
                "category_fit": float(r["score_category_fit"]) if r["score_category_fit"] is not None else None,
                "materiality": float(r["score_materiality"]) if r["score_materiality"] is not None else None,
                "actionability": float(r["score_actionability"]) if r["score_actionability"] is not None else None,
            },
            "confidence": r["confidence"],
            "evidence_references": _jsonb(r.get("evidence_references", [])),
            "metric_signal": _jsonb(r.get("metric_signal", {})),
            "rank": r["rank"],
            "source_format": "module2_trend_shortlist",
        })

    return {"query_context": query_context, "trends": trends}


# ── Module 4: client memories ─────────────────────────────────────

def _row_to_m5_client(r: dict[str, Any]) -> dict[str, Any]:
    """
    Map a module4_client_memories row to one M5 'client' object.
    Field names match Module 4 / First_Run output (no mock CRM schema).
    """
    rid = r.get("run_id", "unknown")
    db_id = r.get("id")
    return {
        "client_id": f"m4_{rid}_{db_id}",
        "name": "Client (Module 4)",
        "persona_tag": "module4_structured_memory",
        "vip_tier": "N/A",
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
        "SELECT id, run_id, raw_voice_note, summary, life_event, timeline, "
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
