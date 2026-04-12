"""
Optional dev helper: push local Module 2 / Module 4 *output-shaped* JSON into Supabase
so you can run M5 with M5_SOURCE=supabase without re-running upstream modules.

  --m2   module_2/outputs/output_shortlist.json  → module2_trend_shortlist
  --m4   module_4/run_log.json                  → module4_client_memories (decision_output)

Does not use mock CRM profiles — only schemas aligned with M2/M4 writers.

Usage:
    python3 module_5/seed_supabase.py --m2
    python3 module_5/seed_supabase.py --m4
    python3 module_5/seed_supabase.py --m2 --m4

Requires SUPABASE_PASSWORD in root .env.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from supabase_client import get_conn, insert_row, insert_rows, is_configured


def seed_m2(conn, path: Path | None = None) -> None:
    path = path or REPO / "module_2" / "outputs" / "output_shortlist.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    shortlist = data.get("shortlist", [])
    if not shortlist:
        print(f"  No shortlist in {path}")
        return

    run_id = data.get("run_id") or "seed_m2"
    rows = []
    for item in shortlist:
        rows.append({
            "run_id": run_id,
            "module1_run_id": data.get("module1_run_id"),
            "brand": data.get("brand"),
            "trend_id": item.get("trend_id"),
            "rank": item.get("rank"),
            "label": item.get("label"),
            "category": item.get("category"),
            "composite_score": item.get("composite_score"),
            "score_freshness": (item.get("scores") or {}).get("freshness"),
            "score_brand_fit": (item.get("scores") or {}).get("brand_fit"),
            "score_category_fit": (item.get("scores") or {}).get("category_fit"),
            "score_materiality": (item.get("scores") or {}).get("materiality"),
            "score_actionability": (item.get("scores") or {}).get("actionability"),
            "confidence": item.get("confidence"),
            "why_selected": item.get("why_selected"),
            "evidence_references": item.get("evidence_references", []),
            "metric_signal": item.get("metric_signal", {}),
        })
    insert_rows(conn, "module2_trend_shortlist", rows)
    print(f"  module2_trend_shortlist: {len(rows)} rows (run_id={run_id}) ← {path.name}")


def seed_m4(conn, path: Path | None = None) -> None:
    path = path or REPO / "module_4" / "run_log.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    decision = data.get("decision_output")
    if not isinstance(decision, dict):
        print(f"  No decision_output in {path}")
        return

    run_id = data.get("run_id", "seed_m4")
    raw = ""
    inp = data.get("input")
    if isinstance(inp, dict):
        raw = inp.get("voice_memo_transcript") or inp.get("transcript") or ""

    insert_row(conn, "module4_client_memories", {
        "run_id": run_id,
        "raw_voice_note": raw,
        "summary": decision.get("summary", ""),
        "life_event": decision.get("life_event", {}),
        "timeline": decision.get("timeline", {}),
        "aesthetic_preference": decision.get("aesthetic_preference", {}),
        "size_height": decision.get("size_height", {}),
        "budget": decision.get("budget", {}),
        "mood": decision.get("mood", {}),
        "trend_signals": decision.get("trend_signals", {}),
        "next_step_intent": decision.get("next_step_intent", {}),
        "model_used": data.get("model_used", ""),
        "confidence_summary": decision.get("confidence_summary", {}),
        "missing_fields_count": decision.get("missing_fields_count", 0),
    })
    print(f"  module4_client_memories: 1 row (run_id={run_id}) ← {path.name}")


def main() -> None:
    p = argparse.ArgumentParser(description="Seed Supabase from M2/M2-shaped JSON files.")
    p.add_argument("--m2", action="store_true", help="Seed module2_trend_shortlist")
    p.add_argument("--m4", action="store_true", help="Seed module4_client_memories")
    args = p.parse_args()

    if not is_configured():
        print("ERROR: SUPABASE_PASSWORD not set in .env")
        sys.exit(1)

    if not args.m2 and not args.m4:
        args.m2 = True
        args.m4 = True

    conn = get_conn()
    try:
        if args.m2:
            print("\n[Module 2]")
            seed_m2(conn)
        if args.m4:
            print("\n[Module 4]")
            seed_m4(conn)
    finally:
        conn.close()
    print("\nDone. Run:  M5_SOURCE=supabase python3 module_5/agent.py")


if __name__ == "__main__":
    main()
