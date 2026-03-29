"""
Module 5 — Outreach Angle Agent MVP
输入: client_memory.json + trend_shortlist.json
输出: outreach建议 + 微信草稿 + run_log.json
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from openai import OpenAI

# 自动加载 .env 文件
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

# ============================================================
# 配置区
# ============================================================
API_KEY = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
if not API_KEY:
    raise ValueError("OPENROUTER_API_KEY not set. Please add it to your .env file or environment.")
MODEL = os.environ.get("DEFAULT_MODEL", "openai/gpt-4o-mini")

# ============================================================
# 文件路径
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_MEMORY_PATH = os.path.join(SCRIPT_DIR, "client_memory.json")
TREND_SHORTLIST_PATH = os.path.join(SCRIPT_DIR, "trend_shortlist.json")
SYSTEM_PROMPT_PATH = os.path.join(SCRIPT_DIR, "system-prompt v2.md")
RUN_LOG_PATH = os.path.join(SCRIPT_DIR, "run_log.json")


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def call_llm(system_prompt, user_prompt):
    client = OpenAI(api_key=API_KEY, base_url="https://openrouter.ai/api/v1")
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
    )
    content = response.choices[0].message.content
    usage = response.usage
    return content, {
        "model": MODEL,
        "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
        "total_tokens": getattr(usage, "total_tokens", 0) or 0,
    }


def parse_agent_output(raw_output):
    text = raw_output.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def display_result(client, result):
    print(f"\n{'='*60}")
    print(f"  {client['client_id']}  {client['name']}  ({client['persona_tag']})")
    print(f"{'='*60}")
    print(f"  Angle:      {result.get('best_angle', 'N/A')}")
    print(f"  Type:       {result.get('outreach_type', 'N/A')}")
    print(f"  Confidence: {result.get('confidence', 'N/A')}")
    print(f"  Strategy:   {result.get('angle_summary', 'N/A')}")

    for i, d in enumerate(result.get("wechat_drafts", []), 1):
        print(f"\n  --- Draft {i} [{d.get('tone', '')}] ---")
        print(f"  {d.get('message', '')}")

    flags = result.get("risk_flags", [])
    if flags:
        print(f"\n  Risks: {', '.join(flags)}")

    print(f"  Next step:  {result.get('next_step', 'N/A')}")


def run_for_client(client, trends_data, system_prompt):
    user_prompt = f"""请为以下客户生成本周 outreach 建议。

## Client Memory
{json.dumps(client, ensure_ascii=False, indent=2)}

## Trend Shortlist
{json.dumps(trends_data, ensure_ascii=False, indent=2)}
"""
    print(f"\n  正在为 {client['name']} ({client['client_id']}) 调用 Claude...")
    raw_output, token_usage = call_llm(system_prompt, user_prompt)
    parsed_output = parse_agent_output(raw_output)

    if parsed_output:
        display_result(client, parsed_output)
    else:
        print(f"\n  ⚠️ {client['name']} 的输出无法解析为 JSON")

    return {
        "run_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "timestamp": datetime.now().isoformat(),
        "model": token_usage["model"],
        "token_usage": token_usage,
        "input": {
            "client_id": client["client_id"],
            "client_name": client["name"],
            "trend_ids": [t["trend_id"] for t in trends_data["trends"]],
        },
        "output": {
            "raw": raw_output,
            "parsed": parsed_output,
        },
        "trace": {
            "retrieved_sources": ["client_memory.json", "trend_shortlist.json"],
            "decision_output": parsed_output.get("best_angle") if parsed_output else None,
            "evidence_used": parsed_output.get("evidence_used") if parsed_output else None,
            "confidence": parsed_output.get("confidence") if parsed_output else None,
            "next_step": parsed_output.get("next_step") if parsed_output else None,
        },
    }


def main():
    print("\n🤖 Module 5 — Outreach Angle Agent MVP")
    print("=" * 60)

    system_prompt = load_text(SYSTEM_PROMPT_PATH)
    clients_data = load_json(CLIENT_MEMORY_PATH)
    trends_data = load_json(TREND_SHORTLIST_PATH)

    all_clients = clients_data["clients"]

    # 如果命令行传了 --all，跑全部客户；否则让用户选
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        clients_to_run = all_clients
        print(f"\n  批量模式：将为 {len(clients_to_run)} 个客户生成建议")
    else:
        print("\n可选客户列表：")
        print("-" * 60)
        for c in all_clients:
            print(f"  {c['client_id']}  {c['name']}  ({c['persona_tag']})  [{c['vip_tier']}]")
        print("-" * 60)
        print("  输入客户ID选择单个客户，或输入 all 跑全部")

        if sys.stdin.isatty():
            choice = input("\n请输入: ").strip()
        else:
            choice = "all"
        if choice.lower() == "all":
            clients_to_run = all_clients
        else:
            match = [c for c in all_clients if c["client_id"] == choice]
            if not match:
                print(f"  未找到 {choice}")
                return
            clients_to_run = match

    run_logs = []
    for client in clients_to_run:
        log_entry = run_for_client(client, trends_data, system_prompt)
        run_logs.append(log_entry)

    with open(RUN_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(run_logs, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 全部完成。{len(run_logs)} 条 run log 已保存: {RUN_LOG_PATH}")

    # ── Supabase sync ──────────────────────────────────────────────
    try:
        import sys as _sys
        from pathlib import Path as _Path
        _sys.path.insert(0, str(_Path(__file__).parent.parent))
        from supabase_writer import write_outreach_suggestion, write_run_log
        from supabase_client import is_configured
        if is_configured():
            from datetime import datetime as _dt
            run_id = _dt.utcnow().strftime("m5_%Y%m%d_%H%M%S")
            for log in run_logs:
                write_outreach_suggestion(run_id, {
                    "client_id":          log.get("client_id", ""),
                    "outreach_angle":     log.get("output", {}).get("outreach_angle", ""),
                    "wechat_draft":       log.get("output", {}).get("wechat_draft", ""),
                    "reasoning":          log.get("output", {}).get("reasoning", ""),
                    "trend_signals_used": log.get("trend_signals_used", []),
                    "client_memory_ref":  log.get("client_memory_summary", {}),
                    "confidence":         log.get("output", {}).get("confidence", ""),
                    "model_used":         MODEL,
                })
            write_run_log(run_id, "", MODEL, "v2", len(run_logs),
                          {"run_logs": run_logs})
            print(f"  [DB] Supabase sync complete ({len(run_logs)} suggestions)")
        else:
            print("  [DB] Supabase skipped (SUPABASE_PASSWORD not set)")
    except Exception as _e:
        print(f"  [DB WARN] Supabase sync skipped: {_e}")


if __name__ == "__main__":
    main()
