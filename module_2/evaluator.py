"""
evaluator.py — LLM evaluation engine for Module 2 Trend Relevance & Materiality Filter Agent.

Uses OpenRouter (OpenAI-compatible) so it shares the same API key and model config
as the rest of the pipeline (OPENROUTER_API_KEY / DEFAULT_MODEL from .env).
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

from prompts import build_system_prompt, build_batch_evaluation_prompt

BATCH_SIZE = 5
TODAY = "2026-03-25"


def _get_client():
    """Initialize OpenAI client pointed at OpenRouter."""
    try:
        from openai import OpenAI
    except ImportError:
        print("[ERROR] openai package not installed. Run: pip install openai")
        sys.exit(1)

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise EnvironmentError(
            "OPENROUTER_API_KEY environment variable is not set. "
            "Please add it to your .env file."
        )
    key_preview = api_key[:8]
    print(f"[evaluator] OPENROUTER_API_KEY: {key_preview}... → OpenRouter client initialized")
    return OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")


def _get_model() -> str:
    return os.environ.get("DEFAULT_MODEL", "anthropic/claude-3-5-sonnet")


def _call_llm(client, model: str, prompt: str, system_prompt: str = "", attempt: int = 1) -> Optional[str]:
    """Call OpenRouter and return raw text. Retries once on failure."""
    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content
    except Exception as e:
        if attempt == 1:
            print(f"  [API error] {e} — retrying in 3s...")
            time.sleep(3)
            return _call_llm(client, model, prompt, system_prompt, attempt=2)
        print(f"  [ERROR] API error on retry: {e}")
        return None


def _parse_llm_response(raw: str, expected_trend_ids: list) -> list:
    """Parse LLM JSON response into list of evaluation dicts."""
    if not raw:
        return []

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"  [ERROR] JSON parse failed: {e}")
        print(f"  [DEBUG] Raw response (first 500 chars): {raw[:500]}")
        return []

    if isinstance(parsed, dict):
        parsed = [parsed]
    elif not isinstance(parsed, list):
        print(f"  [ERROR] Unexpected LLM response type: {type(parsed)}")
        return []

    valid = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        trend_id = item.get("trend_id")
        if not trend_id:
            print(f"  [WARN] Evaluation missing trend_id, skipping: {str(item)[:200]}")
            continue
        if "composite_score" not in item:
            scores = item.get("scores", {})
            if scores:
                cs = (
                    scores.get("freshness", 0) * 0.20
                    + scores.get("brand_fit", 0) * 0.30
                    + scores.get("category_fit", 0) * 0.20
                    + scores.get("materiality", 0) * 0.15
                    + scores.get("actionability", 0) * 0.15
                )
                item["composite_score"] = round(cs, 2)
        valid.append(item)

    return valid


def evaluate_batch(
    trends: list,
    brand_profile: dict,
    client=None,
) -> list:
    """
    Evaluate a list of trend objects using the LLM.
    Processes in batches of BATCH_SIZE.
    """
    if client is None:
        client = _get_client()
    model = _get_model()
    system_prompt = build_system_prompt(brand_profile)

    all_evaluations = []
    total = len(trends)
    batches = [trends[i : i + BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]

    evaluated_count = 0
    for batch_num, batch in enumerate(batches, start=1):
        batch_start = evaluated_count + 1
        batch_end = evaluated_count + len(batch)
        print(
            f"\nEvaluating trends {batch_start}-{batch_end} of {total} "
            f"(batch {batch_num}/{len(batches)}) via {model}..."
        )

        prompt = build_batch_evaluation_prompt(brand_profile, batch, today=TODAY)
        raw_response = _call_llm(client, model, prompt, system_prompt)

        if raw_response is None:
            print(
                f"  [ERROR] Batch {batch_num} failed — "
                f"all {len(batch)} trends in this batch will be skipped"
            )
            evaluated_count += len(batch)
            continue

        batch_ids = [t.get("trend_id") for t in batch]
        evaluations = _parse_llm_response(raw_response, batch_ids)

        if not evaluations:
            print(f"  [ERROR] Could not parse any evaluations from batch {batch_num}")
        else:
            print(
                f"  Successfully parsed {len(evaluations)} evaluation(s) from batch {batch_num}"
            )
            all_evaluations.extend(evaluations)

        evaluated_count += len(batch)

        if batch_num < len(batches):
            time.sleep(1)

    return all_evaluations


def select_shortlist(evaluations: list, max_shortlist: int = 5) -> list:
    """
    From a list of LLM evaluations, select trends that pass qualification criteria
    and return the top N by composite_score.

    Qualification:
    - shortlist == True (LLM judgment)
    - composite_score >= 6.5
    - No individual dimension score below 4
    """
    qualified = []

    for ev in evaluations:
        if not ev.get("shortlist", False):
            continue

        composite = ev.get("composite_score", 0)
        if composite < 6.5:
            ev["shortlist"] = False
            ev["disqualifying_reason"] = (
                ev.get("disqualifying_reason")
                or f"composite_score {composite:.2f} below 6.5 threshold"
            )
            continue

        scores = ev.get("scores", {})
        failed_dim = None
        for dim, score in scores.items():
            if score < 4:
                failed_dim = dim
                break
        if failed_dim:
            ev["shortlist"] = False
            ev["disqualifying_reason"] = (
                ev.get("disqualifying_reason")
                or f"Dimension '{failed_dim}' scored {scores[failed_dim]:.1f} — below minimum of 4"
            )
            continue

        qualified.append(ev)

    qualified.sort(key=lambda x: x.get("composite_score", 0), reverse=True)
    return qualified[:max_shortlist]
