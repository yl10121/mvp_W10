"""
module_3/trend_brief_agent/supabase_writer.py
Writes Module 3 trend brief outputs to Supabase.
Tables: module3_trend_briefs, module3_run_logs
"""
from __future__ import annotations
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from supabase_client import get_conn, insert_row, is_configured
except ImportError:
    def is_configured(): return False


def write_trend_brief(run_id: str, brand: str, city: str,
                      output_markdown: str, output_html: str,
                      trend_cards: list, source_file: str,
                      model_used: str) -> int | None:
    if not is_configured():
        return None
    conn = get_conn()
    new_id = insert_row(conn, "module3_trend_briefs", {
        "run_id":          run_id,
        "brand":           brand,
        "city":            city,
        "output_markdown": output_markdown,
        "output_html":     output_html,
        "trend_cards":     trend_cards,
        "source_file":     source_file,
        "model_used":      model_used,
    })
    conn.close()
    if new_id:
        print(f"  [DB] module3_trend_briefs ← {brand}/{city} (id={new_id})")
    return new_id


def write_run_log(run_id: str, brand: str, city: str,
                  model_used: str, brief_count: int,
                  error: str = "") -> int | None:
    if not is_configured():
        return None
    conn = get_conn()
    new_id = insert_row(conn, "module3_run_logs", {
        "run_id":       run_id,
        "brand":        brand,
        "city":         city,
        "model_used":   model_used,
        "brief_count":  brief_count,
        "error":        error,
    })
    conn.close()
    return new_id
