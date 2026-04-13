"""
Load Module 5 inputs from Supabase only (no local JSON fallback).

  - module2_trend_shortlist → trends_data (optional Top-N via M5_TREND_TOP_N)
  - module4_client_memories → lightweight client picker rows only; full memory
    is fetched per client at generation time (see module_5.agent.run_for_client).

Env:
  SUPABASE_PASSWORD     — required
  M5_MODULE2_RUN_ID     — pin Module 2 shortlist batch (default: latest)
  M5_MODULE4_RUN_ID     — pin Module 4 memory batch (default: latest)
  M5_TREND_TOP_N        — keep only top N trends after load (default 15 if unset; 0 = no limit)
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
import config  # noqa: F401 — 仓库根 .env + OPENROUTER→OPENAI


def _trend_sort_key(t: dict[str, Any]) -> tuple:
    r = t.get("rank")
    if r is None:
        r = 10**9
    try:
        r = int(r)
    except (TypeError, ValueError):
        r = 10**9
    sc = t.get("composite_score")
    try:
        sc = float(sc) if sc is not None else float("-inf")
    except (TypeError, ValueError):
        sc = float("-inf")
    return (r, -sc)


def apply_trend_top_n(trends_data: dict[str, Any]) -> dict[str, Any]:
    """
    Limit trends list length (read-only KB size cap).

    M5_TREND_TOP_N unset → default 15 (short-term upgrade: bounded context).
    M5_TREND_TOP_N=0 → no limit (full shortlist from DB).
    """
    raw = os.environ.get("M5_TREND_TOP_N", "").strip()
    if not raw:
        limit = 15
    else:
        try:
            limit = int(raw)
        except ValueError:
            return trends_data
    if limit <= 0:
        return trends_data
    trends = list(trends_data.get("trends") or [])
    if len(trends) <= limit:
        return trends_data
    ordered = sorted(trends, key=_trend_sort_key)
    out: dict[str, Any] = dict(trends_data)
    out["trends"] = ordered[:limit]
    qc = dict(out.get("query_context") or {})
    qc["m5_trend_limit_applied"] = limit
    qc["m5_trends_total_before_cap"] = len(trends)
    out["query_context"] = qc
    return out


@dataclass
class M5InputBundle:
    clients_data: dict[str, Any]
    trends_data: dict[str, Any]
    sources: dict[str, Any] = field(default_factory=dict)


def load_m5_pipeline_inputs(
    repo_root: object | None = None,
    shortlist_path: str | None = None,
    client_memory_path: str | None = None,
    m4_run_log_path: str | None = None,
) -> M5InputBundle:
    """
    Load M5 inputs from Supabase. Legacy path kwargs are ignored (kept for call-site compatibility).

    Raises:
      ValueError if Supabase is not configured or queries fail.
    """
    del repo_root, shortlist_path, client_memory_path, m4_run_log_path

    from supabase_client import is_configured

    if not is_configured():
        raise ValueError(
            "Supabase is not configured (set SUPABASE_PASSWORD in .env). "
            "Module 5 loads inputs from the database only."
        )

    from module_5.supabase_reader import read_m4_client_summaries, read_trend_shortlist

    trends_data = apply_trend_top_n(read_trend_shortlist())
    if not trends_data.get("trends"):
        raise ValueError("No trends loaded from module2_trend_shortlist.")

    m4_run_id, summaries = read_m4_client_summaries()
    if not summaries:
        raise ValueError(f"No client rows in module4_client_memories for run_id={m4_run_id!r}.")

    return M5InputBundle(
        clients_data={"clients": summaries},
        trends_data=trends_data,
        sources={
            "trend_shortlist_path": "supabase:module2_trend_shortlist",
            "client_source_path": "supabase:module4_client_memories",
            "client_source_kind": "supabase_summaries_only",
            "module4_run_id": m4_run_id,
            "module2_run_id": (trends_data.get("query_context") or {}).get("module2_run_id"),
        },
    )


def main_cli() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Validate M5 Supabase inputs and print sources.")
    p.add_argument("--repo", default=None, help="unused, kept for CLI compatibility")
    args = p.parse_args()
    b = load_m5_pipeline_inputs()
    print(json.dumps(b.sources, ensure_ascii=False, indent=2))
    print(f"client picker rows: {len(b.clients_data.get('clients', []))}")
    print(f"trends:             {len(b.trends_data.get('trends', []))}")


if __name__ == "__main__":
    main_cli()
