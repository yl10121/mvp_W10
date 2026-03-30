"""
Module 5 — Outreach Angle Agent MVP
输入: Module 2 趋势短名单 + Module 4 客户记忆（本地 JSON 或 Supabase，见 pipeline_inputs）
输出: outreach 建议 + 微信草稿 + run_log.json

运行方式:
  python agent.py              # CA 工作台：展示完整客户池 → 输入序号或 ID 圈选 / all 全选
  python agent.py --demo       # 仅展示客户池（不调模型，无需 API key）
  python agent.py --all
  python agent.py --clients BENCH_001,BENCH_003

  Web（最小 CA 页，列表多选）:
  python module_5/web_ca.py   # 仓库根目录执行，默认 http://127.0.0.1:5050
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from openai import OpenAI

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
from pipeline_inputs import load_m5_pipeline_inputs


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


_load_env_file(_REPO_ROOT / ".env")
_load_env_file(Path(__file__).resolve().parent / ".env")

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


def print_ca_client_pool(all_clients: list) -> None:
    """产品侧：在终端展示完整客户池（带序号，便于圈选）。"""
    print("\n")
    print("  ┌─ CA 工作台 · 客户池（完整列表）─────────────────────────────")
    print(f"  │ 共 {len(all_clients)} 人 · 与下方趋势短名单一并作为本次 outreach 输入")
    print("  └──────────────────────────────────────────────────────────────")
    print()
    print(f"  {'序号':>4}  {'client_id':<14}  {'姓名':<18}  persona / VIP")
    print("  " + "-" * 74)
    for i, c in enumerate(all_clients, 1):
        pid = str(c.get("client_id", ""))
        name = str(c.get("name", ""))[:16]
        tag = str(c.get("persona_tag") or "")[:24]
        vip = str(c.get("vip_tier") or "")
        print(f"  {i:4d}  {pid:<14}  {name:<18}  {tag}  [{vip}]")
    print("  " + "-" * 74)


def resolve_ca_selection(choice: str, all_clients: list) -> tuple[list | None, str | None]:
    """
    解析 CA 输入：all 全选；或逗号分隔的「序号」(1-based) 与/或 client_id。
    返回 (clients, None) 或 (None, error_message)。
    """
    raw = choice.strip()
    if not raw:
        return None, "输入为空"
    if raw.lower() == "all":
        return list(all_clients), None
    parts = [x.strip() for x in raw.replace("，", ",").split(",") if x.strip()]
    by_id = {c["client_id"]: c for c in all_clients}
    out: list = []
    for p in parts:
        if p.isdigit():
            i = int(p)
            if i < 1 or i > len(all_clients):
                return None, f"序号 {i} 无效（有效范围 1–{len(all_clients)}）"
            out.append(all_clients[i - 1])
        else:
            if p not in by_id:
                return None, f"未找到 client_id：{p}"
            out.append(by_id[p])
    seen: set[str] = set()
    deduped: list = []
    for c in out:
        cid = c["client_id"]
        if cid not in seen:
            seen.add(cid)
            deduped.append(c)
    return deduped, None


def run_for_client(client, trends_data, system_prompt, retrieved_sources=None):
    user_prompt = f"""请为以下客户生成 **微信私聊用的 outreach 建议**（不是店内导购与顾客面对面说话的脚本）。

**场景**：CA 同时管理多位客户；下方 Client Memory 与 Trend Shortlist 是系统里已有的「客户记忆 + 本季趋势」。常见用途：新品到店想轻触达、想联系一段时间未互动的客户、或需要基于记忆写一句不尴尬的开场。**消息是异步的**：客户不在店员面前，是在手机上看微信。

请按系统提示中的 OPERATING CONTEXT 与 VOICE AND TONE：草稿要像 **CA 打字发出去的短消息**，偏 conversation starter / 轻触达；需要时可点到 **可推荐的新品方向或品类**（来自趋势与记忆的合理衔接），避免写成「现场带您试穿、现在方便吗」一类当面话术。

## Context
- Brand (Maison): {BRAND}

## Client Memory
{json.dumps(client, ensure_ascii=False, indent=2)}

## Trend Shortlist
{json.dumps(trends_data, ensure_ascii=False, indent=2)}
"""
    print(f"\n  正在为 {client['name']} ({client['client_id']}) 调用 Claude...")
    raw_output, token_usage = call_llm(system_prompt, user_prompt)
    parsed_output = parse_agent_output(raw_output)

    if parsed_output is None:
        repair = (
            user_prompt
            + "\n\n你的上一段输出无法被解析为合法 JSON。"
            + "请严格只输出一个符合系统提示中 OUTPUT FORMAT 的 JSON 对象；"
            + "不要使用 markdown 代码块；不要添加任何 JSON 以外的文字。"
        )
        raw_output2, token_usage2 = call_llm(system_prompt, repair, temperature=min(TEMPERATURE, 0.35))
        raw_output = raw_output2
        token_usage = {
            "model": token_usage2["model"],
            "input_tokens": token_usage["input_tokens"] + token_usage2["input_tokens"],
            "output_tokens": token_usage["output_tokens"] + token_usage2["output_tokens"],
            "total_tokens": token_usage["total_tokens"] + token_usage2["total_tokens"],
        }
        parsed_output = parse_agent_output(raw_output)

    if parsed_output:
        display_result(client, parsed_output)
    else:
        print(f"\n  ⚠️ {client['name']} 的输出无法解析为 JSON（已重试一次）")

    trace_sources = retrieved_sources or ["module4_memory", "module2_shortlist"]
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
            "retrieved_sources": trace_sources,
            "decision_output": parsed_output.get("best_angle") if parsed_output else None,
            "evidence_used": parsed_output.get("evidence_used") if parsed_output else None,
            "confidence": parsed_output.get("confidence") if parsed_output else None,
            "next_step": parsed_output.get("next_step") if parsed_output else None,
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Module 5 — 为所选客户生成 outreach（全选 / 圈选 / 单人交互）"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="全选：对当前加载列表中的全部客户各生成一条结果",
    )
    parser.add_argument(
        "--clients",
        default="",
        metavar="IDS",
        help="圈选：序号或 client_id，逗号分隔，例如 1,3,5 或 BENCH_001,BENCH_003",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="仅展示完整客户池（不调模型，无需 API key；体验产品侧列表）",
    )
    args = parser.parse_args()
    if args.all and args.clients.strip():
        parser.error("请只使用 --all 或 --clients 之一，不要同时指定")
    if args.demo and (args.all or args.clients.strip()):
        parser.error("--demo 不能与 --all / --clients 同时使用")

    print("\n🤖 Module 5 — Outreach Angle Agent MVP")
    print("=" * 60)

    system_prompt = load_text(SYSTEM_PROMPT_PATH)
    bundle = load_m5_pipeline_inputs(repo_root=_REPO_ROOT)
    clients_data = bundle.clients_data
    trends_data = bundle.trends_data
    src = bundle.sources
    retrieved = [
        src.get("client_source_path", ""),
        src.get("trend_shortlist_path", ""),
    ]
    print("\n[输入] 数据源:")
    print(f"  趋势短名单: {src.get('trend_shortlist_path')}")
    print(f"  客户记忆:   {src.get('client_source_path')} ({src.get('client_source_kind')})")

    all_clients = clients_data["clients"]

    if args.demo:
        print_ca_client_pool(all_clients)
        print(
            "  以上为当前加载的完整客户池（预览结束）。\n"
            "  若要圈选并生成 outreach：在本机终端执行\n"
            "    python3 module_5/agent.py\n"
            "  按提示输入序号、client_id 或 all；或直接使用：\n"
            "    python3 module_5/agent.py --clients 1,2,3\n"
        )
        return

    if args.all:
        clients_to_run = all_clients
        print(f"\n  全选：将为 {len(clients_to_run)} 个客户各调用一次模型并汇总结果")
    elif args.clients.strip():
        clients_to_run, err = resolve_ca_selection(args.clients, all_clients)
        if err:
            print(f"  错误：{err}")
            return
        if not clients_to_run:
            print("  错误：未选中任何客户")
            return
        print(f"\n  圈选：已选 {len(clients_to_run)} 个客户，将各调用一次模型")
    else:
        print_ca_client_pool(all_clients)
        print("  ── 请选择本次要生成 outreach 的客户 ──")
        print("    · 输入 all — 全选上面列表中的全部客户")
        print("    · 输入序号 — 一人：3  或多人：1,3,5（逗号分隔，对应上表序号）")
        print("    · 输入 client_id — 一人：BENCH_001  或多人：BENCH_001,BENCH_003")

        if sys.stdin.isatty():
            choice = input("\n  请输入（然后回车）: ").strip()
        else:
            choice = "all"
        if choice.lower() == "all":
            print(f"\n  已确认全选：共 {len(clients_to_run)} 人，将各调用一次模型")
        else:
            print(f"\n  已确认圈选：共 {len(clients_to_run)} 人，将各调用一次模型")

    run_logs = []
    for client in clients_to_run:
        log_entry = run_for_client(
            client, trends_data, system_prompt, retrieved_sources=retrieved
        )
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
                inp = log.get("input") or {}
                parsed = (log.get("output") or {}).get("parsed") or {}
                drafts = parsed.get("wechat_drafts") or []
                first_msg = drafts[0].get("message", "") if drafts else ""
                write_outreach_suggestion(run_id, {
                    "client_id":          inp.get("client_id", ""),
                    "outreach_angle":     parsed.get("best_angle", ""),
                    "wechat_draft":       first_msg,
                    "reasoning":          parsed.get("angle_summary", ""),
                    "trend_signals_used": parsed.get("evidence_used", []),
                    "client_memory_ref":  {
                        "client_id": inp.get("client_id"),
                        "trend_ids": inp.get("trend_ids", []),
                        "evidence_used": parsed.get("evidence_used"),
                    },
                    "confidence":         parsed.get("confidence", ""),
                    "model_used":         MODEL,
                })
            first_cid = (run_logs[0].get("input") or {}).get("client_id", "") if run_logs else ""
            write_run_log(run_id, first_cid, MODEL, PROMPT_VERSION, len(run_logs),
                          {"run_logs": run_logs})
            print(f"  [DB] Supabase sync complete ({len(run_logs)} suggestions)")
        else:
            print("  [DB] Supabase skipped (SUPABASE_PASSWORD not set)")
    except Exception as _e:
        print(f"  [DB WARN] Supabase sync skipped: {_e}")


if __name__ == "__main__":
    main()
