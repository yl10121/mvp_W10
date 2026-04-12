"""
将 module_5/run_log.json 转为易读 Markdown（无需任何云服务或密钥）。

用法（仓库根目录）:
  python3 module_5/run_log_to_markdown.py

可选环境变量:
  M5_RUN_LOG_PATH   — 输入 JSON，默认 module_5/run_log.json
  M5_RUN_LOG_MD_PATH — 输出 md，默认 module_5/run_log.md
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_M5 = Path(__file__).resolve().parent
_REPO = _M5.parent
if str(_M5) not in sys.path:
    sys.path.insert(0, str(_M5))

from runlog_export_common import load_run_log


def _md_escape(s: str) -> str:
    return s.replace("\r\n", "\n").replace("\r", "\n")


def entry_to_markdown(entry: dict, index: int) -> str:
    inp = entry.get("input") or {}
    out = entry.get("output") or {}
    parsed = out.get("parsed")
    if not isinstance(parsed, dict):
        parsed = {}
    tok = entry.get("token_usage") or {}
    cid = inp.get("client_id", "?")
    name = inp.get("client_name", "")
    lines: list[str] = []
    lines.append(f"## {index}. `{cid}` · {name}")
    lines.append("")
    lines.append(f"- **模型**: {entry.get('model', '')}")
    lines.append(f"- **时间**: {entry.get('timestamp', '')}")
    if tok:
        lines.append(
            f"- **Token**: 约 {tok.get('total_tokens', '')}（in {tok.get('input_tokens', '')} / out {tok.get('output_tokens', '')}）"
        )
    lines.append("")
    if not parsed:
        lines.append("*（本条无解析后的 `parsed` 字段）*")
        lines.append("")
        return "\n".join(lines)

    lines.append(f"- **最佳角度**: {parsed.get('best_angle', '')}")
    lines.append(f"- **类型**: {parsed.get('outreach_type', '')}")
    lines.append(f"- **信心**: {parsed.get('confidence', '')}")
    lines.append("")
    lines.append("### 策略摘要")
    lines.append("")
    lines.append(_md_escape(str(parsed.get("angle_summary", "") or "—")))
    lines.append("")
    ev = parsed.get("evidence_used")
    if isinstance(ev, list) and ev:
        lines.append("### 依据 / 证据")
        lines.append("")
        for x in ev:
            lines.append(f"- {_md_escape(str(x))}")
        lines.append("")
    drafts = parsed.get("wechat_drafts") or []
    if drafts:
        lines.append("### 微信草稿")
        lines.append("")
        for i, d in enumerate(drafts, 1):
            tone = d.get("tone", "") if isinstance(d, dict) else ""
            msg = d.get("message", "") if isinstance(d, dict) else ""
            lines.append(f"**草稿 {i}**（{tone}）")
            lines.append("")
            lines.append("```")
            lines.append(_md_escape(str(msg)))
            lines.append("```")
            lines.append("")
    rf = parsed.get("risk_flags")
    if isinstance(rf, list) and rf:
        lines.append("### 风险提示")
        lines.append("")
        for x in rf:
            lines.append(f"- {_md_escape(str(x))}")
        lines.append("")
    dns = parsed.get("do_not_say")
    if isinstance(dns, list) and dns:
        lines.append("### 避免提及")
        lines.append("")
        for x in dns:
            lines.append(f"- {_md_escape(str(x))}")
        lines.append("")
    lines.append("### 下一步建议")
    lines.append("")
    lines.append(_md_escape(str(parsed.get("next_step", "") or "—")))
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    in_path = Path(os.environ.get("M5_RUN_LOG_PATH", "").strip() or (_M5 / "run_log.json")).resolve()
    out_path = Path(os.environ.get("M5_RUN_LOG_MD_PATH", "").strip() or (_M5 / "run_log.md")).resolve()
    data = load_run_log(in_path)
    parts: list[str] = []
    parts.append("# Module 5 · Outreach 运行结果（可读版）")
    parts.append("")
    parts.append(f"> 由 `run_log.json` 自动生成 · 共 **{len(data)}** 位客户")
    parts.append("")
    parts.append(f"> 源文件: `{in_path}`")
    parts.append("")
    parts.append("---")
    parts.append("")
    for i, entry in enumerate(data, 1):
        parts.append(entry_to_markdown(entry, i))
    text = "\n".join(parts).rstrip() + "\n"
    out_path.write_text(text, encoding="utf-8")
    print(f"已写入: {out_path}")


if __name__ == "__main__":
    main()
