"""
M1 商品目录检索（RAG）：用客户记忆 + 趋势知识库拼成 query，对 SKU 文本做向量相似度 Top-K；
嵌入走 OpenRouter /v1/embeddings；失败时回退为简单词重叠打分。

Env:
  M5_CATALOG_RAG_TOP_K   — 默认 10
  M5_CATALOG_EMBED_MODEL — 默认 openai/text-embedding-3-small（需在 OpenRouter 可用）
"""

from __future__ import annotations

import json
import math
import os
import re
from typing import Any

_RE_TOKEN = re.compile(
    r"[\u4e00-\u9fff]{2,}|[a-zA-Z0-9]+(?:[-'][a-zA-Z0-9]+)*",
    re.UNICODE,
)


def _tokens(text: str) -> set[str]:
    return {m.group(0).lower() for m in _RE_TOKEN.finditer(text or "")}


def _lexical_scores(query: str, docs: list[str]) -> list[float]:
    q = _tokens(query)
    if not q:
        return [0.0] * len(docs)
    return [float(len(q & _tokens(d))) for d in docs]


def _cosine(a: list[float], b: list[float]) -> float:
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


def product_document(row: dict[str, Any]) -> str:
    parts = [
        str(row.get("name") or ""),
        str(row.get("brand") or ""),
        str(row.get("category") or ""),
        str(row.get("description") or ""),
        json.dumps(row.get("attributes") or {}, ensure_ascii=False),
    ]
    return "\n".join(p for p in parts if p.strip())


def _memory_text_chunks(mem: dict[str, Any]) -> list[str]:
    out: list[str] = []
    skip = {"memory_row_id", "m4_run_id"}
    for k, v in mem.items():
        if k in skip:
            continue
        if isinstance(v, str) and v.strip():
            out.append(v.strip())
        elif isinstance(v, dict):
            val = v.get("value")
            if isinstance(val, str) and val.strip() and val.strip().upper() != "N/A":
                out.append(val.strip())
            ev = v.get("evidence")
            if isinstance(ev, str) and len(ev.strip()) > 3:
                out.append(ev.strip()[:500])
    return out


def build_retrieval_query(mem: dict[str, Any], trend_kb: dict[str, Any]) -> str:
    parts = _memory_text_chunks(mem)
    for t in (trend_kb or {}).get("trends") or []:
        if not isinstance(t, dict):
            continue
        for key in ("trend_label", "cluster_summary", "category", "subcategory"):
            v = t.get(key)
            if isinstance(v, str) and v.strip():
                parts.append(v.strip()[:600])
    text = "\n".join(parts)
    return text[:12000]


def _embed_batches(texts: list[str], api_key: str, model: str) -> list[list[float]]:
    from openai import OpenAI

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={
            "HTTP-Referer": os.environ.get("OPENROUTER_HTTP_REFERER", "https://github.com/m-ny-mvp"),
            "X-Title": os.environ.get("OPENROUTER_X_TITLE", "M5 Catalog RAG"),
        },
    )
    batch = 32
    all_rows: list[tuple[int, list[float]]] = []
    for start in range(0, len(texts), batch):
        chunk = texts[start : start + batch]
        resp = client.embeddings.create(model=model, input=chunk)
        for item in resp.data:
            rel = int(getattr(item, "index", 0))
            emb = list(item.embedding)
            all_rows.append((start + rel, emb))
    all_rows.sort(key=lambda x: x[0])
    return [e for _, e in all_rows]


def retrieve_top_products(
    rows: list[dict[str, Any]],
    mem: dict[str, Any],
    trend_kb: dict[str, Any],
    top_k: int,
    api_key: str,
    embed_model: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    meta: dict[str, Any] = {
        "embed_model": embed_model,
        "top_k": top_k,
        "candidates": len(rows),
        "method": None,
    }
    if not rows or top_k <= 0:
        return [], meta

    query = build_retrieval_query(mem, trend_kb)
    meta["query_chars"] = len(query)
    docs = [product_document(r) for r in rows]

    scores: list[float]
    if api_key.strip() and embed_model.strip():
        try:
            combined = docs + [query]
            vectors = _embed_batches(combined, api_key, embed_model)
            if len(vectors) != len(combined):
                raise RuntimeError(f"embedding count mismatch {len(vectors)} != {len(combined)}")
            qv = vectors[-1]
            dvs = vectors[:-1]
            scores = [_cosine(qv, dv) for dv in dvs]
            meta["method"] = "embedding"
        except Exception as e:
            meta["embed_error"] = str(e)[:300]
            scores = _lexical_scores(query, docs)
            meta["method"] = "lexical_fallback"
    else:
        scores = _lexical_scores(query, docs)
        meta["method"] = "lexical"

    order = sorted(range(len(rows)), key=lambda i: scores[i], reverse=True)
    top_idx = order[:top_k]
    meta["top_scores"] = [round(scores[i], 5) for i in top_idx]
    return [rows[i] for i in top_idx], meta
