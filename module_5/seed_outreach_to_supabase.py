"""
把 benchmark 数据（M2 趋势 + M4 客户记忆）以及已有的 run_log.json（M5 输出）
一次性写入 Supabase，满足 Week 10 Part B2 要求。

用法:
    python3 module_5/seed_outreach_to_supabase.py          # 全量：M2 + M4 + M5
    python3 module_5/seed_outreach_to_supabase.py --m5     # 仅 M5 outreach suggestions
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from supabase_client import get_conn, insert_row, is_configured

M5_DIR = REPO / "module_5"
BENCH_DIR = M5_DIR / "benchmark"
TRENDS_PATH = BENCH_DIR / "benchmark_trend_shortlist.json"
CLIENTS_PATH = BENCH_DIR / "benchmark_clients.json"
RUN_LOG_PATH = M5_DIR / "run_log.json"


def seed_m2_trends(conn) -> int:
    """Insert benchmark trends into module2_trend_shortlist."""
    with open(TRENDS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    qc = data.get("query_context", {})
    run_id = qc.get("module2_run_id") or "bench_m2_x"
    trends = data.get("trends", [])
    count = 0
    for t in trends:
        scores = t.get("scores", {})
        row = {
            "run_id": run_id,
            "module1_run_id": qc.get("module1_run_id", ""),
            "brand": qc.get("brand", "Louis Vuitton"),
            "trend_id": t["trend_id"],
            "rank": t.get("rank"),
            "label": t.get("trend_label", ""),
            "category": t.get("category", ""),
            "composite_score": t.get("composite_score"),
            "score_freshness": scores.get("freshness"),
            "score_brand_fit": scores.get("brand_fit"),
            "score_category_fit": scores.get("category_fit"),
            "score_materiality": scores.get("materiality"),
            "score_actionability": scores.get("actionability"),
            "confidence": t.get("confidence", ""),
            "why_selected": t.get("cluster_summary", ""),
            "evidence_references": t.get("evidence_references", []),
            "metric_signal": t.get("metric_signal", {}),
        }
        if insert_row(conn, "module2_trend_shortlist", row) is not None:
            count += 1
    print(f"  module2_trend_shortlist: {count}/{len(trends)} rows inserted (run_id={run_id})")
    return count


def seed_m4_clients(conn) -> int:
    """Insert benchmark clients into module4_client_memories."""
    with open(CLIENTS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    clients = data.get("clients", [])
    count = 0
    for c in clients:
        run_id = c.get("module4_run_id", "bench_m4_20260330")
        row = {
            "run_id": run_id,
            "raw_voice_note": c.get("raw_voice_note", ""),
            "summary": c.get("summary", ""),
            "life_event": c.get("life_event", {}),
            "timeline": c.get("timeline", {}),
            "aesthetic_preference": c.get("aesthetic_preference", {}),
            "size_height": c.get("size_height", {}),
            "budget": c.get("budget", {}),
            "mood": c.get("mood", {}),
            "trend_signals": c.get("trend_signals", {}),
            "next_step_intent": c.get("next_step_intent", {}),
            "model_used": c.get("model_used", "benchmark_generator/1.0"),
            "confidence_summary": c.get("confidence_summary", {}),
            "missing_fields_count": c.get("missing_fields_count", 0),
        }
        if insert_row(conn, "module4_client_memories", row) is not None:
            count += 1
    print(f"  module4_client_memories: {count}/{len(clients)} rows inserted")
    return count


def seed_m5_outreach(conn) -> int:
    """Insert run_log.json entries into module5_outreach_suggestions + module5_run_logs."""
    with open(RUN_LOG_PATH, "r", encoding="utf-8") as f:
        run_logs = json.load(f)

    from datetime import datetime
    batch_run_id = f"m5_seed_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    count = 0
    for log in run_logs:
        inp = log.get("input", {})
        parsed = (log.get("output") or {}).get("parsed") or {}
        if not parsed:
            continue

        drafts = parsed.get("wechat_drafts", [])
        first_msg = drafts[0].get("message", "") if drafts else ""

        evidence = parsed.get("evidence_used", [])
        trend_ids = inp.get("trend_ids", [])

        row = {
            "run_id": batch_run_id,
            "client_id": inp.get("client_id", ""),
            "outreach_angle": parsed.get("best_angle", ""),
            "wechat_draft": first_msg,
            "reasoning": parsed.get("angle_summary", ""),
            "trend_signals_used": evidence,
            "client_memory_ref": {
                "client_id": inp.get("client_id"),
                "trend_ids": trend_ids,
                "evidence_used": evidence,
            },
            "confidence": parsed.get("confidence", ""),
            "model_used": log.get("model", ""),
        }
        if insert_row(conn, "module5_outreach_suggestions", row) is not None:
            count += 1

    first_cid = run_logs[0]["input"]["client_id"] if run_logs else ""
    insert_row(conn, "module5_run_logs", {
        "run_id": batch_run_id,
        "client_id": first_cid,
        "model_used": run_logs[0].get("model", "") if run_logs else "",
        "prompt_version": "v2",
        "suggestions_count": count,
        "run_log_raw": run_logs,
    })

    print(f"  module5_outreach_suggestions: {count}/{len(run_logs)} rows inserted (run_id={batch_run_id})")
    print(f"  module5_run_logs: 1 row inserted")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Supabase with benchmark + M5 output data.")
    parser.add_argument("--m5", action="store_true", help="Only seed M5 outreach suggestions")
    args = parser.parse_args()

    if not is_configured():
        print("ERROR: SUPABASE_PASSWORD not set in .env")
        sys.exit(1)

    conn = get_conn()
    try:
        if not args.m5:
            print("\n[Step 1] Seeding Module 2 trends...")
            seed_m2_trends(conn)
            print("\n[Step 2] Seeding Module 4 client memories...")
            seed_m4_clients(conn)

        print("\n[Step 3] Seeding Module 5 outreach suggestions...")
        seed_m5_outreach(conn)
    finally:
        conn.close()

    print("\n✅ Done. Supabase populated.")


if __name__ == "__main__":
    main()
