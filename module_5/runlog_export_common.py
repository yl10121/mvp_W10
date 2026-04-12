"""Shared helpers: load run_log.json and flatten output.parsed into tabular rows."""

from __future__ import annotations

import json
from pathlib import Path


def load_run_log(path: Path) -> list:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("run_log.json 应为数组")
    return data


def flatten_row(entry: dict) -> list[str]:
    inp = entry.get("input") or {}
    out = entry.get("output") or {}
    parsed = out.get("parsed")
    if not isinstance(parsed, dict):
        parsed = {}
    tok = entry.get("token_usage") or {}
    drafts = parsed.get("wechat_drafts") or []
    d0 = drafts[0] if len(drafts) > 0 else {}
    d1 = drafts[1] if len(drafts) > 1 else {}

    def _join_list(x):
        if not x:
            return ""
        if isinstance(x, list):
            return " | ".join(str(i) for i in x)
        return str(x)

    return [
        str(inp.get("client_id", "")),
        str(inp.get("client_name", "")),
        str(parsed.get("best_angle", "")),
        str(parsed.get("outreach_type", "")),
        str(parsed.get("angle_summary", "")),
        str(parsed.get("confidence", "")),
        str(d0.get("tone", "")),
        str(d0.get("message", "")),
        str(d1.get("tone", "")),
        str(d1.get("message", "")),
        _join_list(parsed.get("evidence_used")),
        _join_list(parsed.get("risk_flags")),
        _join_list(parsed.get("do_not_say")),
        str(parsed.get("next_step", "")),
        str(entry.get("timestamp", "")),
        str(tok.get("total_tokens", "")),
        str(entry.get("model", "")),
    ]


HEADERS = [
    "client_id",
    "client_name",
    "best_angle",
    "outreach_type",
    "angle_summary",
    "confidence",
    "draft1_tone",
    "draft1_message",
    "draft2_tone",
    "draft2_message",
    "evidence_used",
    "risk_flags",
    "do_not_say",
    "next_step",
    "run_timestamp",
    "total_tokens",
    "model",
]
