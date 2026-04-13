"""
Module 5 — Outreach Angle Agent MVP
输入: Supabase — module2_trend_shortlist（经 Top-N + 只读知识库视图进模型）+ module4_client_memories
      （列表仅轻量字段；调用模型前按人所选从数据库拉取该客户完整记忆，等价「按需 tool」）
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

import anthropic

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
import config  # noqa: F401 — 仓库根 .env + OPENROUTER→OPENAI 单钥传播
from pipeline_inputs import load_m5_pipeline_inputs
from module_5.supabase_reader import fetch_m4_client_full_by_pk
from module_5.trend_kb import build_readonly_trend_kb


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
API_KEY = os.environ.get("ANTHROPIC_API_KEY") or ""
MODEL = os.environ.get("DEFAULT_MODEL", "openai/gpt-4o-mini")
BRAND = os.environ.get("BRAND", "Louis Vuitton")


def _env_float(key: str, default: float) -> float:
    v = os.environ.get(key, "").strip()
    if not v:
        return default
    try:
        return float(v)
    except ValueError:
        return default


TEMPERATURE = _env_float("M5_TEMPERATURE", 0.55)
PROMPT_VERSION = os.environ.get("M5_PROMPT_VERSION", "v2").strip() or "v2"


def _brand_catalog_block(mem: dict, trend_kb: dict) -> tuple[str, dict]:
    """
    M1 商品目录：默认 RAG Top-K（向量检索 + 词重叠回退）；M5_CATALOG_RAG=0 时为截断全量列表。
    返回 (prompt_json 片段, 追溯用 meta)。
    """
    meta: dict = {}
    if os.environ.get("M5_INCLUDE_BRAND_CATALOG", "1").strip() in ("0", "false", "no"):
        return "", meta
    try:
        from supabase_client import is_configured

        if not is_configured():
            return "", meta
        from module_1.supabase_reader import read_brand_products

        rows = read_brand_products(brand=BRAND)
        if not rows:
            return "", meta

        rag_on = os.environ.get("M5_CATALOG_RAG", "1").strip().lower() not in (
            "0",
            "false",
            "no",
            "off",
        )
        if not rag_on:
            raw_max = os.environ.get("M5_CATALOG_PROMPT_MAX", "40").strip() or "40"
            try:
                max_n = int(raw_max)
            except ValueError:
                max_n = 40
            picked = rows if max_n <= 0 else rows[:max_n]
            meta = {"method": "full_list_truncated", "rows": len(picked)}
            return json.dumps(picked, ensure_ascii=False, indent=2), meta

        try:
            top_k = int(os.environ.get("M5_CATALOG_RAG_TOP_K", "10").strip() or "10")
        except ValueError:
            top_k = 10
        embed_model = (
            os.environ.get("M5_CATALOG_EMBED_MODEL", "openai/text-embedding-3-small").strip()
        )
        api_key = (
            os.environ.get("OPENROUTER_API_KEY", "").strip()
            or os.environ.get("OPENAI_API_KEY", "").strip()
        )
        from module_5.catalog_rag import retrieve_top_products

        picked, rmeta = retrieve_top_products(rows, mem, trend_kb, top_k, api_key, embed_model)
        meta = dict(rmeta)
        if not picked:
            return "", meta
        return json.dumps(picked, ensure_ascii=False, indent=2), meta
    except Exception as e:
        return "", {"error": str(e)[:200]}


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


def call_llm(system_prompt, user_prompt, temperature: float | None = None):
    """
    优先 OpenRouter：设置了 OPENROUTER_API_KEY（或 ANTHROPIC_API_BASE_URL 指向 openrouter）时
    走 OpenAI 兼容 /chat/completions；否则直连 Anthropic Messages API。
    """
    t = TEMPERATURE if temperature is None else temperature
    _base = os.environ.get("ANTHROPIC_API_BASE_URL", "").strip()
    _or_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    _use_openrouter = bool(_or_key) or ("openrouter" in _base.lower())
    if _use_openrouter:
        from openai import OpenAI

        key = _or_key or API_KEY
        if not key:
            raise ValueError(
                "OpenRouter：请设置 OPENROUTER_API_KEY 或 ANTHROPIC_API_KEY（可填同一 OpenRouter key）"
            )
        or_base = _base if "openrouter" in _base.lower() else "https://openrouter.ai/api/v1"
        client = OpenAI(
            base_url=or_base.rstrip("/"),
            api_key=key,
            default_headers={
                "HTTP-Referer": os.environ.get("OPENROUTER_HTTP_REFERER", "https://github.com/m-ny-mvp"),
                "X-Title": os.environ.get("OPENROUTER_X_TITLE", "Module 5 Outreach"),
            },
        )
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=4096,
            temperature=t,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = (response.choices[0].message.content or "").strip()
        u = response.usage
        pt = getattr(u, "prompt_tokens", None) or 0
        ct = getattr(u, "completion_tokens", None) or 0
        return content, {
            "model": MODEL,
            "input_tokens": pt,
            "output_tokens": ct,
            "total_tokens": pt + ct,
        }

    if not API_KEY:
        raise ValueError(
            "未配置 LLM：请设置 OPENROUTER_API_KEY（推荐）或 ANTHROPIC_API_KEY，并写入 .env。"
        )
    _kw = {"api_key": API_KEY}
    if _base:
        _kw["base_url"] = _base
    client = anthropic.Anthropic(**_kw)
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        temperature=t,
    )
    content = response.content[0].text
    usage = response.usage
    return content, {
        "model": MODEL,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.input_tokens + usage.output_tokens,
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


def run_for_client(client, trends_data, system_prompt, retrieved_sources=None, m4_run_id=None):
    """
    client: 轻量 picker 行（含 memory_row_id）或已是完整记忆 dict。
    若提供 m4_run_id 且 client 含 memory_row_id，则在调用模型前从 Supabase 拉取该行完整记忆。
    """
    mem = client
    if m4_run_id and client.get("memory_row_id") is not None:
        try:
            mem = fetch_m4_client_full_by_pk(m4_run_id, int(client["memory_row_id"]))
        except Exception as e:
            print(f"\n  ⚠️ 无法拉取客户完整记忆 id={client.get('memory_row_id')}: {e}")
            raise

    trend_kb = build_readonly_trend_kb(trends_data)
    catalog_json, catalog_meta = _brand_catalog_block(mem, trend_kb)
    catalog_section = ""
    if catalog_json:
        catalog_section = f"""
## Brand product catalog (read-only, M1, RAG Top-K)
以下为根据**当前客户记忆 + 本批趋势知识库**从目录中检索出的相关 SKU（非全量表）。引用时请以块内字段为准，勿编造未出现的规格或价格。
{catalog_json}
"""
    user_prompt = f"""请为以下客户生成 **微信私聊用的 outreach 建议**（不是店内导购与顾客面对面说话的脚本）。

**场景**：CA 同时管理多位客户；下方 Client Memory 与 **Trend Shortlist（只读知识库）** 是系统里已有的「客户记忆 + 本批可参考趋势」。趋势块为**只读参考**，用于分析与引用，不可当作可编辑数据。常见用途：新品到店想轻触达、想联系一段时间未互动的客户、或需要基于记忆写一句不尴尬的开场。**消息是异步的**：客户不在店员面前，是在手机上看微信。

请按系统提示中的 OPERATING CONTEXT 与 VOICE AND TONE：草稿要像 **CA 打字发出去的短消息**，偏 conversation starter / 轻触达；需要时可点到 **可推荐的新品方向或品类**（来自趋势与记忆的合理衔接），避免写成「现场带您试穿、现在方便吗」一类当面话术。

## Context
- Brand (Maison): {BRAND}

## Client Memory
{json.dumps(mem, ensure_ascii=False, indent=2)}

## Trend Shortlist (read-only knowledge base)
{json.dumps(trend_kb, ensure_ascii=False, indent=2)}
{catalog_section}"""
    print(f"\n  正在为 {mem['name']} ({mem['client_id']}) 调用 LLM...")
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
        display_result(mem, parsed_output)
    else:
        print(f"\n  ⚠️ {mem['name']} 的输出无法解析为 JSON（已重试一次）")

    trace_sources = list(retrieved_sources or ["module4_memory", "module2_shortlist"])
    if catalog_json:
        trace_sources.append("module1_brand_products_rag")
    return {
        "run_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "timestamp": datetime.now().isoformat(),
        "model": token_usage["model"],
        "token_usage": token_usage,
        "input": {
            "client_id": mem["client_id"],
            "client_name": mem["name"],
            "trend_ids": [t["trend_id"] for t in trends_data["trends"]],
        },
        "output": {
            "raw": raw_output,
            "parsed": parsed_output,
        },
        "trace": {
            "retrieved_sources": trace_sources,
            "catalog_rag": catalog_meta or None,
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
    print(f"  M4 run_id:  {src.get('module4_run_id', '')}")

    m4_run_id = src.get("module4_run_id")
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
            client,
            trends_data,
            system_prompt,
            retrieved_sources=retrieved,
            m4_run_id=m4_run_id,
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
