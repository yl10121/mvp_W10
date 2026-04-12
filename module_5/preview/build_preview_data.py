"""
合并 ../run_log.json 与 ../benchmark/benchmark_clients.json → preview_data.json
供静态页 fetch 使用。在 module_5/preview 目录执行:

  python3 build_preview_data.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_PREVIEW = Path(__file__).resolve().parent
_M5 = _PREVIEW.parent


def main() -> None:
    run_path = _M5 / "run_log.json"
    bench_path = _M5 / "benchmark" / "benchmark_clients.json"
    if not run_path.is_file():
        print(f"缺少 {run_path}", file=sys.stderr)
        sys.exit(1)
    if not bench_path.is_file():
        print(f"缺少 {bench_path}", file=sys.stderr)
        sys.exit(1)

    with open(run_path, "r", encoding="utf-8") as f:
        run_log = json.load(f)
    with open(bench_path, "r", encoding="utf-8") as f:
        bench = json.load(f)
    clients_meta = {c["client_id"]: c for c in bench.get("clients", []) if isinstance(c, dict)}

    out: list[dict] = []
    for entry in run_log:
        inp = entry.get("input") or {}
        cid = inp.get("client_id", "")
        meta = clients_meta.get(cid, {})
        parsed = (entry.get("output") or {}).get("parsed")
        if not isinstance(parsed, dict):
            parsed = {}
        out.append(
            {
                "client_id": cid,
                "name": meta.get("name") or inp.get("client_name", ""),
                "persona_tag": meta.get("persona_tag", ""),
                "vip_tier": meta.get("vip_tier", ""),
                "summary": meta.get("summary", ""),
                "best_angle": parsed.get("best_angle", ""),
                "angle_summary": parsed.get("angle_summary", ""),
                "outreach_type": parsed.get("outreach_type", ""),
                "confidence": parsed.get("confidence", ""),
                "evidence_used": parsed.get("evidence_used") or [],
                "wechat_drafts": parsed.get("wechat_drafts") or [],
                "next_step": parsed.get("next_step", ""),
                "risk_flags": parsed.get("risk_flags") or [],
            }
        )

    out_path = _PREVIEW / "preview_data.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"已写入 {out_path}，共 {len(out)} 条")


if __name__ == "__main__":
    main()
