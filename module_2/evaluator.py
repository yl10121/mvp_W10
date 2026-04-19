"""
evaluator.py — LLM evaluation engine for Module 2 Trend Relevance & Materiality Filter Agent.

Uses OpenRouter (OpenAI-compatible) so it shares the same API key and model config
as the rest of the pipeline (OPENROUTER_API_KEY / DEFAULT_MODEL from .env).

Composite score formula:
  brand_fit × 0.25 + ca_conversational_utility × 0.25 + trend_velocity × 0.20
  + language_specificity × 0.15 + novelty × 0.10 + cross_run_persistence × 0.05

LLM scores 4 dimensions: brand_fit, ca_conversational_utility, language_specificity, novelty.
trend_velocity and cross_run_persistence are computed algorithmically from
engagement_recency_pct and run_count stored on each trend object by scorer.py.
Persona matching and product recommendations are Module 3's responsibility.
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

SCORE_WEIGHTS = {
    "brand_fit": 0.25,
    "ca_conversational_utility": 0.25,
    "trend_velocity": 0.20,
    "language_specificity": 0.15,
    "novelty": 0.10,
    "cross_run_persistence": 0.05,
}


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


def _compute_trend_velocity(engagement_recency_pct: float) -> float:
    """
    Convert engagement_recency_pct (% of engagement from last 7 days) to 0-10 score.
    >70% recent → 8-10 | 40-70% → 5-7 | <40% → 1-4
    """
    if engagement_recency_pct >= 70:
        return round(8.0 + (engagement_recency_pct - 70) / 30 * 2, 1)
    elif engagement_recency_pct >= 40:
        return round(5.0 + (engagement_recency_pct - 40) / 30 * 2, 1)
    else:
        return round(max(1.0, 1.0 + engagement_recency_pct / 40 * 3), 1)


def _compute_cross_run_persistence(run_count: int) -> float:
    """
    Convert number of runs a trend appeared in to 0-10 score.
    Real XHS trends typically appear in 1 run — 1 run scores 5 (not disqualifying).
    ≥3 runs → 10 | 2 runs → 7 | 1 run → 5
    """
    if run_count >= 3:
        return 10.0
    return {2: 7.0}.get(run_count, 5.0)


def _compute_composite(scores: dict) -> float:
    """Compute composite score using Week 11 weights."""
    return round(
        sum(scores.get(dim, 0) * weight for dim, weight in SCORE_WEIGHTS.items()),
        2,
    )


def _call_llm(
    client,
    model: str,
    prompt: str,
    system_prompt: str = "",
    attempt: int = 1,
) -> Optional[str]:
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


def _extract_partial_json_objects(text: str) -> list:
    """
    Given a truncated JSON string (e.g. a cut-off array), extract every complete
    top-level JSON object {...} that can be parsed independently.
    Used as fallback when the full response fails to parse.
    """
    objects = []
    depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                candidate = text[start: i + 1]
                try:
                    obj = json.loads(candidate)
                    objects.append(obj)
                except json.JSONDecodeError:
                    pass
                start = None
    return objects


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
        print(f"  [WARN] JSON parse failed ({e}) — attempting partial recovery...")
        parsed = _extract_partial_json_objects(cleaned)
        if parsed:
            print(f"  [WARN] Recovered {len(parsed)} complete object(s) from truncated response")
        else:
            print(f"  [ERROR] No recoverable objects in response")
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
        # composite_score will be recomputed after adding algorithmic dimensions
        # but store LLM-provided one as a reference if present
        valid.append(item)

    return valid


_PROMPT_MAX_SNIPPETS = 3    # max evidence snippets sent to LLM per trend
_PROMPT_MAX_SNIPPET_CHARS = 200  # max characters per snippet


def _slim_for_prompt(trend: dict) -> dict:
    """
    Return a lightweight copy of a trend object safe to include in an LLM prompt.
    Keeps: trend_id, label, category, summary, metrics, extracted_product,
           engagement_recency_pct, run_count, no_date_signal, low_signal_warning,
           evidence.snippets (≤3, ≤200 chars each).
    Drops: evidence.posts[] entirely — post bodies are large and not needed by the LLM;
           the scorer already digested them into snippets and metrics.
    """
    evidence = trend.get("evidence", {})
    raw_snippets = evidence.get("snippets", [])

    # Truncate snippets: max 3, max 200 chars each
    trimmed_snippets = [
        s[:_PROMPT_MAX_SNIPPET_CHARS] if len(s) > _PROMPT_MAX_SNIPPET_CHARS else s
        for s in raw_snippets[:_PROMPT_MAX_SNIPPETS]
    ]

    slimmed = {
        "trend_id": trend.get("trend_id"),
        "label": trend.get("label"),
        "category": trend.get("category"),
        "summary": trend.get("summary"),
        "metrics": trend.get("metrics"),
        "evidence": {"snippets": trimmed_snippets},
        "engagement_recency_pct": trend.get("engagement_recency_pct"),
        "run_count": trend.get("run_count", 1),
    }
    # Include flags and extraction result if present
    for optional in ("extracted_product", "no_date_signal", "low_signal_warning"):
        if trend.get(optional):
            slimmed[optional] = trend[optional]

    return slimmed


def evaluate_batch(
    trends: list,
    brand_profile: dict,
    client=None,
) -> list:
    """
    Evaluate a list of trend objects using the LLM.
    Processes in batches of BATCH_SIZE.
    Trend objects are slimmed before prompt construction to avoid 128k token limits —
    posts[] is dropped entirely; snippets capped at 3 × 200 chars.
    After LLM evaluation, adds algorithmically computed dimensions
    (trend_velocity, cross_run_persistence) and recomputes composite_score.
    """
    if client is None:
        client = _get_client()
    model = _get_model()
    system_prompt = build_system_prompt(brand_profile)

    # Build lookup for trend metadata (engagement_recency_pct, run_count, no_date_signal)
    trend_meta = {
        t.get("trend_id"): {
            "engagement_recency_pct": t.get("engagement_recency_pct", 0.0),
            "run_count": t.get("run_count", 1),
            "no_date_signal": bool(t.get("no_date_signal", False)),
        }
        for t in trends
    }

    all_evaluations = []
    total = len(trends)
    batches = [trends[i: i + BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]

    evaluated_count = 0
    for batch_num, batch in enumerate(batches, start=1):
        batch_start = evaluated_count + 1
        batch_end = evaluated_count + len(batch)
        print(
            f"\nEvaluating trends {batch_start}-{batch_end} of {total} "
            f"(batch {batch_num}/{len(batches)}) via {model}..."
        )

        slim_batch = [_slim_for_prompt(t) for t in batch]
        prompt = build_batch_evaluation_prompt(brand_profile, slim_batch, today=TODAY)
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
            # Attach algorithmic dimensions and recompute composite_score
            for ev in evaluations:
                tid = ev.get("trend_id")
                meta = trend_meta.get(tid, {})

                recency_pct = meta.get("engagement_recency_pct", 0.0)
                run_count = meta.get("run_count", 1)
                no_date_signal = meta.get("no_date_signal", False)

                # If no post dates exist, recency_pct is meaningless (defaults to 0).
                # Use a neutral 5.0 so trend_velocity doesn't disqualify good trends
                # that simply lacked date metadata. Only compute from real data when
                # we actually have dates.
                if no_date_signal:
                    trend_velocity = 5.0
                else:
                    trend_velocity = _compute_trend_velocity(recency_pct)
                cross_run_persistence = _compute_cross_run_persistence(run_count)

                scores = ev.get("scores", {})
                scores["trend_velocity"] = trend_velocity
                scores["cross_run_persistence"] = cross_run_persistence
                ev["scores"] = scores

                # Recompute composite with new formula
                ev["composite_score"] = _compute_composite(scores)

                # Store computed metadata for reporting
                ev["engagement_recency_pct"] = recency_pct
                ev["run_count"] = run_count
                ev["no_date_signal"] = no_date_signal

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
        no_date = ev.get("no_date_signal", False)

        # cross_run_persistence minimum is 3 (real trends naturally appear in 1 run)
        # ca_conversational_utility minimum is 4 (category-linkable trends score 6-7; only
        #   purely abstract trends score 1-3 and should be disqualified)
        # trend_velocity is skipped when no_date_signal is True — it was set to neutral 5.0
        #   and using it as a disqualifier would punish trends for missing metadata, not quality
        # all other LLM-scored dimensions minimum is 4
        DIM_MINIMUMS = {
            "cross_run_persistence": 3,
            "ca_conversational_utility": 4,
        }
        # client_persona_match and category_fit removed — not scored in this module
        SKIP_DIM_MINIMUMS = {"trend_velocity"} if no_date else set()

        failed_dim = None
        for dim, score in scores.items():
            if dim in SKIP_DIM_MINIMUMS:
                continue
            if isinstance(score, (int, float)):
                min_score = DIM_MINIMUMS.get(dim, 4)
                if score < min_score:
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
