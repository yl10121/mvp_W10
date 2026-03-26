"""
module_4/supabase_writer.py
Writes Module 4 client memory extractions to Supabase.
Tables: module4_client_memories, module4_run_logs
"""
from __future__ import annotations
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from supabase_client import get_conn, insert_row, is_configured
except ImportError:
    def is_configured(): return False


def write_client_memory(run_id: str, raw_voice_note: str,
                        memory_obj: dict[str, Any],
                        model_used: str = "") -> int | None:
    if not is_configured():
        return None
    conn = get_conn()
    conf = memory_obj.get("confidence_summary", {})
    new_id = insert_row(conn, "module4_client_memories", {
        "run_id":               run_id,
        "raw_voice_note":       raw_voice_note,
        "summary":              memory_obj.get("summary", ""),
        "life_event":           memory_obj.get("life_event", {}),
        "timeline":             memory_obj.get("timeline", {}),
        "aesthetic_preference": memory_obj.get("aesthetic_preference", {}),
        "size_height":          memory_obj.get("size_height", {}),
        "budget":               memory_obj.get("budget", {}),
        "mood":                 memory_obj.get("mood", {}),
        "trend_signals":        memory_obj.get("trend_signals", {}),
        "next_step_intent":     memory_obj.get("next_step_intent", {}),
        "model_used":           model_used,
        "confidence_summary":   conf,
        "missing_fields_count": memory_obj.get("missing_fields_count", 0),
    })
    conn.close()
    if new_id:
        print(f"  [DB] module4_client_memories ← run={run_id} (id={new_id})")
    return new_id


def write_run_log(run_id: str, model_used: str,
                  records_processed: int = 0) -> int | None:
    if not is_configured():
        return None
    conn = get_conn()
    new_id = insert_row(conn, "module4_run_logs", {
        "run_id":            run_id,
        "model_used":        model_used,
        "records_processed": records_processed,
    })
    conn.close()
    return new_id
