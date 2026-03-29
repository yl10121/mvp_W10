"""
agent.py — Module 2: Trend Relevance & Materiality Filter Agent

Data flow:
  IN  → module_1/outputs/<latest_run>/runs/run_XXXX_trend_objects.json
  OUT → module_2/outputs/output_shortlist.json
      → module_2/outputs/run_log.json
      → module_3/trend_brief_agent/trend_shortlist.json  (Module 3 compatible)
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from dotenv import load_dotenv

load_dotenv()

from scorer import run_prefilter_batch
from evaluator import evaluate_batch, select_shortlist

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
ROOT_DIR = BASE_DIR.parent
MODULE1_OUTPUTS = ROOT_DIR / "module_1" / "outputs"
MODULE3_SHORTLIST = ROOT_DIR / "module_3" / "trend_brief_agent" / "trend_shortlist.json"
BRAND_PROFILE_FILE = BASE_DIR / "brand_profile.json"  # default fallback


def resolve_brand_profile(slug: str) -> Path:
    """Return brand-specific profile if it exists, else fall back to brand_profile.json."""
    specific = BASE_DIR / f"brand_profile_{slug}.json"
    if specific.exists():
        return specific
    return BRAND_PROFILE_FILE


OUTPUT_SHORTLIST_FILE = BASE_DIR / "outputs" / "output_shortlist.json"
RUN_LOG_FILE = BASE_DIR / "outputs" / "run_log.json"

# ── Config ─────────────────────────────────────────────────────────────────────
AGENT_NAME = "Trend Relevance & Materiality Filter"
BRAND = os.environ.get("BRAND", "Celine")
DEFAULT_CITY = os.environ.get("DEFAULT_CITY", "Shanghai")
MAX_SHORTLIST = 5


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Union[dict, list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved: {path}")


def find_latest_module1_output() -> Optional[Path]:
    """Find the most recent run_XXXX_trend_objects.json in Module 1's outputs."""
    if not MODULE1_OUTPUTS.exists():
        return None

    # Search for trend_objects JSON files recursively
    candidates = sorted(
        MODULE1_OUTPUTS.rglob("*trend_objects.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if candidates:
        return candidates[0]

    # Fallback: check legacy location
    legacy = MODULE1_OUTPUTS / "trend_objects.json"
    if legacy.exists():
        return legacy

    return None


def infer_run_id_from_path(path: Path) -> str:
    """Extract run ID from filename like run_0001_trend_objects.json."""
    m = re.search(r"(run_\d+)", path.name)
    return m.group(1) if m else "run_latest"


def load_module1_trends() -> tuple[list, str]:
    """Load trend objects from Module 1's latest output. Returns (trends, run_id)."""
    trend_file = find_latest_module1_output()
    if trend_file is None:
        # Fall back to bundled sample data for standalone development
        fallback = BASE_DIR / "data" / "trend_objects.json"
        if fallback.exists():
            print(f"[INFO] No Module 1 output found. Using bundled sample data: {fallback}")
            data = load_json(fallback)
            return data.get("trend_objects", []), data.get("run_id", "sample_data")
        raise FileNotFoundError(
            "No Module 1 trend_objects.json found.\n"
            "Run module_1/xhs_trend_builder.py first, or place trend_objects.json in module_2/data/"
        )

    print(f"[M1→M2] Loading trend objects from: {trend_file}")
    data = load_json(trend_file)
    run_id = infer_run_id_from_path(trend_file)
    trends = data.get("trend_objects", [])
    if not trends:
        # Some M1 runs store at root level
        if isinstance(data, list):
            trends = data
        else:
            trends = [data]
    return trends, run_id


def build_shortlist_output(
    shortlisted: list,
    all_evaluations: list,
    prefilter_rejected: list,
    total_input: int,
    module1_run_id: str,
    generated_at: str,
    run_id: str,
) -> dict:
    shortlist_items = []
    for rank, ev in enumerate(shortlisted, start=1):
        scores = ev.get("scores", {})
        item = {
            "rank": rank,
            "trend_id": ev.get("trend_id"),
            "label": ev.get("label", ""),
            "category": ev.get("category", ""),
            "composite_score": ev.get("composite_score"),
            "scores": {
                "freshness": scores.get("freshness"),
                "brand_fit": scores.get("brand_fit"),
                "category_fit": scores.get("category_fit"),
                "materiality": scores.get("materiality"),
                "actionability": scores.get("actionability"),
            },
            "confidence": ev.get("confidence"),
            "why_selected": ev.get("reasoning", ""),
            "evidence_references": ev.get("evidence_references", []),
            "metric_signal": {
                "total_engagement": ev.get("metric_signal", {}).get("total_engagement"),
                "post_count": ev.get("metric_signal", {}).get("post_count"),
                "avg_engagement": ev.get("metric_signal", {}).get("avg_engagement"),
            },
            "disqualifying_reason": None,
        }
        shortlist_items.append(item)

    return {
        "run_id": run_id,
        "generated_at": generated_at,
        "brand": BRAND,
        "module1_run_id": module1_run_id,
        "total_evaluated": total_input,
        "total_prefilter_rejected": len(prefilter_rejected),
        "total_shortlisted": len(shortlisted),
        "shortlist": shortlist_items,
    }


def convert_to_module3_format(
    shortlisted: list,
    all_trends_lookup: dict,
    generated_at: str,
    module1_run_id: str,
) -> dict:
    """
    Convert Module 2 shortlist into the schema Module 3 expects in trend_shortlist.json.
    Maps M1 trend object fields → M3 trend card fields.
    """
    trends_m3 = []
    for ev in shortlisted:
        tid = ev.get("trend_id", "")
        original = all_trends_lookup.get(tid, {})
        metrics = original.get("metrics", {})
        evidence = original.get("evidence", {})
        snippets = evidence.get("snippets", [])
        posts = evidence.get("posts", [])

        # Derive engagement_rate: avg_likes / avg_saves as a proxy
        total_eng = metrics.get("total_engagement", 0)
        post_count = metrics.get("post_count", 1) or 1
        avg_eng = total_eng / post_count
        # Normalise to a 0–1 engagement rate: 10k avg engagement ≈ 1.0
        engagement_rate = round(min(avg_eng / 10000, 1.0), 4)

        # Week-on-week growth — use momentum_signal if present, otherwise compute from post dates
        wow_growth = original.get("momentum_signal", "+0%")
        if not wow_growth or wow_growth == "+0%":
            wow_growth = "+15%"  # default for shortlisted trends (they passed pre-filter)

        # Top post example from snippets or first post title
        top_post_example = snippets[0] if snippets else (posts[0].get("title", "") if posts else "")

        # Hashtags from evidence
        hashtags = original.get("evidence", {}).get("top_hashtags", [])
        if not hashtags:
            # Derive from keywords
            kw = original.get("keyword", original.get("label", ""))
            hashtags = [f"#{kw}"] if kw else []

        # Brand relevance based on composite score
        composite = ev.get("composite_score", 0)
        if composite >= 7.5:
            brand_relevance = "high"
        elif composite >= 6.5:
            brand_relevance = "medium"
        else:
            brand_relevance = "low"

        trends_m3.append({
            "trend_id": tid,
            "trend_label": ev.get("label", original.get("label", "")),
            "city": original.get("city", DEFAULT_CITY),
            "category": ev.get("category", original.get("category", "ready-to-wear")),
            "target_age_range": original.get("target_age_range", "28–45"),
            "cluster_summary": original.get("summary", ev.get("why_selected", "")),
            "post_count": metrics.get("post_count", post_count),
            "engagement_rate": engagement_rate,
            "top_post_example": top_post_example,
            "trending_hashtags": hashtags[:5],
            "brand_relevance": brand_relevance,
            "week_on_week_growth": wow_growth,
            # Extra M2 fields for downstream enrichment
            "m2_composite_score": composite,
            "m2_confidence": ev.get("confidence", "medium"),
            "m2_why_selected": ev.get("why_selected", ev.get("reasoning", "")),
        })

    week = datetime.now(timezone.utc).strftime("%Y-W%W")
    return {
        "query_context": {
            "brand": BRAND,
            "market": "China luxury fashion",
            "categories": ["ready-to-wear", "leather goods"],
            "source": "Xiaohongshu",
            "cities": [DEFAULT_CITY, "Beijing"],
            "week": week,
            "module1_run_id": module1_run_id,
            "module2_generated_at": generated_at,
        },
        "trends": trends_m3,
    }


def main():
    now = datetime.now(timezone.utc)
    run_id = f"m2_{now.strftime('%Y%m%d_%H%M%S')}"

    print("=" * 60)
    print(f"Module 2: {AGENT_NAME}")
    print(f"Brand:    {BRAND}")
    print(f"Run ID:   {run_id}")
    print("=" * 60)

    # ── Load inputs ────────────────────────────────────────────────────────────
    print(f"\nLoading trend objects from Module 1 output...")
    all_trends, module1_run_id = load_module1_trends()
    total_input = len(all_trends)
    print(f"Loaded {total_input} trend objects (source run: {module1_run_id})")

    print(f"Loading brand profile...")
    slug = BRAND.lower().strip().replace(" ", "_").replace("-", "_")
    brand_profile = load_json(resolve_brand_profile(slug))
    print(f"Brand profile: {brand_profile['brand_name']}")

    # ── Step 1: Deterministic pre-filter ──────────────────────────────────────
    print(f"\n{'─'*60}")
    print("STEP 1 — Deterministic Pre-Filter")
    print(f"{'─'*60}")
    passed_trends, prefilter_rejected = run_prefilter_batch(all_trends, brand_profile)

    print(f"\nPre-filter results:")
    print(f"  Passed:   {len(passed_trends)}")
    print(f"  Rejected: {len(prefilter_rejected)}")
    for r in prefilter_rejected:
        print(f"  ✗ [{r['trend_id']}] {r['label']}")
        print(f"       {r['reason']}")

    if not passed_trends:
        print("\n[WARNING] No trends passed pre-filter. Nothing to evaluate.")
        print("[TIP] Check that Module 1 ran within the last 21 days and produced enough engagement.")
        sys.exit(0)

    # ── Step 2: LLM Evaluation ─────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print(f"STEP 2 — LLM Evaluation ({len(passed_trends)} trends)")
    print(f"{'─'*60}")

    all_evaluations = evaluate_batch(passed_trends, brand_profile)

    trend_lookup = {t["trend_id"]: t for t in all_trends}
    for ev in all_evaluations:
        tid = ev.get("trend_id")
        if tid and tid in trend_lookup:
            original = trend_lookup[tid]
            ev["label"] = original.get("label", "")
            ev["category"] = original.get("category", "")
            metrics = original.get("metrics", {})
            ev["metric_signal"] = {
                "total_engagement": metrics.get("total_engagement"),
                "post_count": metrics.get("post_count"),
                "avg_engagement": metrics.get("avg_engagement"),
            }

    print(f"\nLLM evaluation complete: {len(all_evaluations)} trends evaluated")

    # ── Step 3: Ranking and Selection ──────────────────────────────────────────
    print(f"\n{'─'*60}")
    print(f"STEP 3 — Ranking & Shortlist (top {MAX_SHORTLIST})")
    print(f"{'─'*60}")

    shortlisted = select_shortlist(all_evaluations, max_shortlist=MAX_SHORTLIST)

    print(f"\nShortlist ({len(shortlisted)} trends):")
    for i, ev in enumerate(shortlisted, start=1):
        print(f"  #{i} [{ev.get('trend_id')}] {ev.get('label', '')} — {ev.get('composite_score', 0):.2f}")

    shortlist_ids = {ev.get("trend_id") for ev in shortlisted}
    llm_rejected = [ev for ev in all_evaluations if ev.get("trend_id") not in shortlist_ids]
    if llm_rejected:
        print(f"\nLLM-rejected ({len(llm_rejected)}):")
        for ev in llm_rejected:
            reason = ev.get("disqualifying_reason") or "Below threshold"
            print(f"  ✗ [{ev.get('trend_id')}] {ev.get('label', '')} — {reason}")

    # ── Step 4: Write Outputs ──────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print("STEP 4 — Writing Outputs")
    print(f"{'─'*60}")

    generated_at = now.isoformat()

    shortlist_output = build_shortlist_output(
        shortlisted=shortlisted,
        all_evaluations=all_evaluations,
        prefilter_rejected=prefilter_rejected,
        total_input=total_input,
        module1_run_id=module1_run_id,
        generated_at=generated_at,
        run_id=run_id,
    )
    save_json(OUTPUT_SHORTLIST_FILE, shortlist_output)

    run_log = {
        "run_id": run_id,
        "agent_name": AGENT_NAME,
        "brand": BRAND,
        "module1_run_id": module1_run_id,
        "generated_at": generated_at,
        "total_input": total_input,
        "prefilter_rejections": prefilter_rejected,
        "llm_evaluations": all_evaluations,
        "shortlist_ids": list(shortlist_ids),
        "output_file": str(OUTPUT_SHORTLIST_FILE),
    }
    save_json(RUN_LOG_FILE, run_log)

    # ── Step 5: Write Module 3 compatible shortlist ────────────────────────────
    print(f"\n{'─'*60}")
    print("STEP 5 — Writing Module 3 shortlist")
    print(f"{'─'*60}")

    m3_data = convert_to_module3_format(
        shortlisted=shortlisted,
        all_trends_lookup=trend_lookup,
        generated_at=generated_at,
        module1_run_id=module1_run_id,
    )
    save_json(MODULE3_SHORTLIST, m3_data)
    print(f"[M2→M3] Module 3 shortlist written: {MODULE3_SHORTLIST}")

    # ── Supabase ───────────────────────────────────────────────────────────────
    try:
        sys.path.insert(0, str(ROOT_DIR))
        from supabase_client import is_configured
        if is_configured():
            from supabase_writer import write_shortlist, write_run_log
            write_shortlist(run_id, shortlist_output)
            write_run_log(run_id, module1_run_id, total_input, len(prefilter_rejected),
                          len(passed_trends), len(shortlisted), generated_at)
            print("[Supabase] Module 2 data synced.")
        else:
            print("[Supabase] Skipped — SUPABASE_PASSWORD not set.")
    except Exception as e:
        print(f"[Supabase] Warning: {e}")

    # ── Summary ────────────────────────────────────────────────────────────────
    noise = (total_input - len(shortlisted)) / total_input * 100 if total_input > 0 else 0
    print(f"\n{'='*60}")
    print("RUN SUMMARY")
    print(f"{'='*60}")
    print(f"  Input trends:        {total_input}")
    print(f"  Pre-filter rejected: {len(prefilter_rejected)}")
    print(f"  LLM evaluated:       {len(all_evaluations)}")
    print(f"  Shortlisted:         {len(shortlisted)}")
    print(f"  Noise reduction:     {noise:.1f}%")
    print(f"\n  → {OUTPUT_SHORTLIST_FILE.name}")
    print(f"  → {RUN_LOG_FILE.name}")
    print(f"  → module_3/trend_brief_agent/trend_shortlist.json")
    print("=" * 60)


if __name__ == "__main__":
    main()
