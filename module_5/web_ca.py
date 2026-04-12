"""
Module 5 — 最小 CA Web 工作台（本地）
  展示客户池 → 多选 / 全选 → 生成 outreach

用法（在仓库根目录）:
  pip install flask
  export M5_TREND_SHORTLIST_PATH=...   # 可选，见 pipeline_inputs
  export M5_CLIENT_MEMORY_PATH=...
  python module_5/web_ca.py

浏览器打开 http://127.0.0.1:5050
仅本机访问（127.0.0.1），勿暴露到公网。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from flask import Flask, render_template_string, request, url_for

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "module_5") not in sys.path:
    sys.path.insert(0, str(ROOT / "module_5"))

import agent as m5

app = Flask(__name__)

PAGE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Module 5 · CA 工作台</title>
  <style>
    :root { --bg:#faf9f7; --card:#fff; --border:#e8e4de; --text:#1a1a1a; --muted:#666; --accent:#2c2c2c; }
    * { box-sizing: border-box; }
    body { font-family: ui-sans-serif, system-ui, -apple-system, "PingFang SC", sans-serif;
           background: var(--bg); color: var(--text); margin: 0; padding: 24px; line-height: 1.5; }
    h1 { font-size: 1.25rem; font-weight: 600; margin: 0 0 8px; }
    .sub { color: var(--muted); font-size: 0.875rem; margin-bottom: 20px; }
    .card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 20px; max-width: 960px; }
    .toolbar { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 16px; }
    button, .btn { background: var(--accent); color: #fff; border: none; padding: 10px 18px; border-radius: 8px;
                    font-size: 0.9rem; cursor: pointer; text-decoration: none; display: inline-block; }
    button.secondary { background: #fff; color: var(--accent); border: 1px solid var(--border); }
    table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
    th, td { text-align: left; padding: 10px 8px; border-bottom: 1px solid var(--border); vertical-align: top; }
    th { color: var(--muted); font-weight: 500; }
    tr:hover td { background: #f7f5f2; }
    input[type="checkbox"] { width: 18px; height: 18px; accent-color: var(--accent); }
    .err { color: #b42318; margin-top: 12px; font-size: 0.875rem; }
    .result { margin-top: 24px; padding-top: 20px; border-top: 1px solid var(--border); }
    .result h2 { font-size: 1rem; margin: 0 0 12px; }
    .client-block { margin-bottom: 20px; padding: 16px; background: #f7f5f2; border-radius: 8px; }
    .client-block h3 { margin: 0 0 8px; font-size: 0.95rem; }
    .draft { white-space: pre-wrap; font-size: 0.85rem; margin: 8px 0; padding: 10px; background: #fff; border-radius: 6px; border: 1px solid var(--border); }
    code { font-size: 0.8rem; color: var(--muted); }
  </style>
</head>
<body>
  <div class="card">
    <h1>CA 工作台 · 客户池</h1>
    <p class="sub">共 {{ n }} 位客户 · 趋势：<code>{{ trend_src }}</code> · 记忆：<code>{{ client_src }}</code></p>

    <form method="post" action="{{ url_run }}" id="f">
      <div class="toolbar">
        <button type="button" class="secondary" onclick="document.querySelectorAll('.cid').forEach(c=>c.checked=true)">全选</button>
        <button type="button" class="secondary" onclick="document.querySelectorAll('.cid').forEach(c=>c.checked=false)">全不选</button>
        <button type="submit">生成选中客户 outreach</button>
      </div>

      <table>
        <thead>
          <tr>
            <th style="width:40px"></th>
            <th style="width:48px">#</th>
            <th>client_id</th>
            <th>姓名</th>
            <th>persona</th>
            <th>VIP</th>
          </tr>
        </thead>
        <tbody>
        {% for c in clients %}
          <tr>
            <td><input class="cid" type="checkbox" name="client_id" value="{{ c.client_id }}"/></td>
            <td>{{ loop.index }}</td>
            <td>{{ c.client_id }}</td>
            <td>{{ c.name }}</td>
            <td>{{ c.persona_tag or '' }}</td>
            <td>{{ c.vip_tier or '' }}</td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
    </form>

    {% if error %}
    <p class="err">{{ error }}</p>
    {% endif %}

    {% if results %}
    <div class="result">
      <h2>生成结果（{{ results|length }} 人）</h2>
      {% for r in results %}
      <div class="client-block">
        <h3>{{ r.name }} <code>{{ r.client_id }}</code></h3>
        {% if r.parsed %}
        <p><strong>Angle:</strong> {{ r.parsed.best_angle or '' }}</p>
        <p><strong>策略:</strong> {{ r.parsed.angle_summary or '' }}</p>
        {% for d in r.parsed.wechat_drafts or [] %}
          <div class="draft"><strong>[{{ d.tone or 'draft' }}]</strong><br/>{{ d.message or '' }}</div>
        {% endfor %}
        <p><strong>Next:</strong> {{ r.parsed.next_step or '' }}</p>
        {% else %}
        <p class="err">未能解析模型输出，请查看 run_log.json</p>
        {% endif %}
      </div>
      {% endfor %}
      <p><code>完整 JSON 已写入 module_5/run_log.json</code></p>
      <p><a class="btn secondary" href="{{ url_home }}">返回重选</a></p>
    </div>
    {% endif %}
  </div>
</body>
</html>
"""


def _bundle():
    return m5.load_m5_pipeline_inputs(repo_root=ROOT)


def _sync_supabase(run_logs: list) -> None:
    try:
        mp = str(ROOT / "module_5")
        if mp not in sys.path:
            sys.path.insert(0, mp)
        from supabase_writer import write_outreach_suggestion, write_run_log
        from supabase_client import is_configured

        if not is_configured():
            return
        from datetime import datetime as _dt

        run_id = _dt.utcnow().strftime("m5_%Y%m%d_%H%M%S")
        for log in run_logs:
            inp = log.get("input") or {}
            parsed = (log.get("output") or {}).get("parsed") or {}
            drafts = parsed.get("wechat_drafts") or []
            first_msg = drafts[0].get("message", "") if drafts else ""
            write_outreach_suggestion(
                run_id,
                {
                    "client_id": inp.get("client_id", ""),
                    "outreach_angle": parsed.get("best_angle", ""),
                    "wechat_draft": first_msg,
                    "reasoning": parsed.get("angle_summary", ""),
                    "trend_signals_used": parsed.get("evidence_used", []),
                    "client_memory_ref": {
                        "client_id": inp.get("client_id"),
                        "trend_ids": inp.get("trend_ids", []),
                        "evidence_used": parsed.get("evidence_used"),
                    },
                    "confidence": parsed.get("confidence", ""),
                    "model_used": m5.MODEL,
                },
            )
        first_cid = (run_logs[0].get("input") or {}).get("client_id", "") if run_logs else ""
        write_run_log(
            run_id,
            first_cid,
            m5.MODEL,
            m5.PROMPT_VERSION,
            len(run_logs),
            {"run_logs": run_logs},
        )
    except Exception:
        pass


@app.route("/", methods=["GET", "POST"])
def index():
    error = None
    results = None
    bundle = _bundle()
    clients = bundle.clients_data["clients"]
    src = bundle.sources
    trend_src = src.get("trend_shortlist_path", "")
    client_src = src.get("client_source_path", "")

    if request.method == "POST":
        ids = request.form.getlist("client_id")
        if not ids:
            error = "请至少勾选一位客户。"
        else:
            by_id = {c["client_id"]: c for c in clients}
            missing = [i for i in ids if i not in by_id]
            if missing:
                error = "无效 client_id: " + ", ".join(missing)
            else:
                selected = [by_id[i] for i in ids]
                system_prompt = m5.load_text(m5.SYSTEM_PROMPT_PATH)
                retrieved = [client_src, trend_src]
                run_logs = []
                for client in selected:
                    run_logs.append(
                        m5.run_for_client(
                            client,
                            bundle.trends_data,
                            system_prompt,
                            retrieved_sources=retrieved,
                        )
                    )
                with open(m5.RUN_LOG_PATH, "w", encoding="utf-8") as f:
                    json.dump(run_logs, f, ensure_ascii=False, indent=2)
                _sync_supabase(run_logs)
                results = []
                for log in run_logs:
                    inp = log.get("input") or {}
                    parsed = (log.get("output") or {}).get("parsed")
                    results.append(
                        {
                            "client_id": inp.get("client_id", ""),
                            "name": inp.get("client_name", ""),
                            "parsed": parsed,
                        }
                    )
                return render_template_string(
                    PAGE,
                    n=len(clients),
                    trend_src=trend_src,
                    client_src=client_src,
                    clients=clients,
                    error=None,
                    results=results,
                    url_run=url_for("index"),
                    url_home=url_for("index"),
                )

    return render_template_string(
        PAGE,
        n=len(clients),
        trend_src=trend_src,
        client_src=client_src,
        clients=clients,
        error=error,
        results=results,
        url_run=url_for("index"),
        url_home=url_for("index"),
    )


def main():
    port = int(os.environ.get("M5_WEB_PORT", "5050"))
    print(f"\n  Module 5 CA Web · http://127.0.0.1:{port}\n  Ctrl+C 停止\n")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
