"""
module_5/supabase_writer.py
Writes Module 5 outreach suggestions to Supabase.
Tables: module5_outreach_suggestions, module5_run_logs
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


def write_outreach_suggestion(run_id: str,
                               suggestion: dict[str, Any]) -> int | None:
    if not is_configured():
        return None
    conn = get_conn()
    new_id = insert_row(conn, "module5_outreach_suggestions", {
        "run_id":               run_id,
        "client_id":            suggestion.get("client_id", ""),
        "outreach_angle":       suggestion.get("outreach_angle", ""),
        "wechat_draft":         suggestion.get("wechat_draft", ""),
        "reasoning":            suggestion.get("reasoning", ""),
        "trend_signals_used":   suggestion.get("trend_signals_used", []),
        "client_memory_ref":    suggestion.get("client_memory_ref", {}),
        "confidence":           suggestion.get("confidence", ""),
        "model_used":           suggestion.get("model_used", ""),
    })
    conn.close()
    if new_id:
        print(f"  [DB] module5_outreach_suggestions ← run={run_id} (id={new_id})")
    return new_id


def write_run_log(run_id: str, client_id: str, model_used: str,
                  prompt_version: str, suggestions_count: int,
                  run_log_raw: dict) -> int | None:
    if not is_configured():
        return None
    conn = get_conn()
    new_id = insert_row(conn, "module5_run_logs", {
        "run_id":             run_id,
        "client_id":          client_id,
        "model_used":         model_used,
        "prompt_version":     prompt_version,
        "suggestions_count":  suggestions_count,
        "run_log_raw":        run_log_raw,
    })
    conn.close()
    return new_id
