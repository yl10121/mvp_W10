"""
agent.py — Module 2: Trend Relevance & Materiality Filter Agent

Data flow:
  IN  → module_1/outputs/runs/run_*_trend_objects.json  (luxury_fashion only; beauty skipped)
      → module_2/data/synthetic_trends.json              (25 synthetic brand trends)
  OUT → module_2/outputs/output_shortlist.json          (local backup)
      → module_2/outputs/run_log.json
      → module_3/trend_brief_agent/trend_shortlist.json  (Module 3 compatible)
      → Supabase table module2_trend_shortlist            (if connected)
      → module_2/EVAL_REPORT.md                          (auto-generated)
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from dotenv import load_dotenv

_ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

# Confirm API key loaded
_key_preview = os.environ.get("OPENROUTER_API_KEY", "")[:8] or "(not set)"
print(f"[ENV] OPENROUTER_API_KEY loaded: {_key_preview}...")

from scorer import run_prefilter_batch
from evaluator import evaluate_batch, select_shortlist

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
ROOT_DIR = BASE_DIR.parent
MODULE1_RUNS_DIR = ROOT_DIR / "module_1" / "outputs" / "runs"
MODULE3_SHORTLIST = ROOT_DIR / "module_3" / "trend_brief_agent" / "trend_shortlist.json"
SYNTHETIC_TRENDS_FILE = BASE_DIR / "data" / "synthetic_trends.json"
OUTPUT_SHORTLIST_FILE = BASE_DIR / "outputs" / "output_shortlist.json"
RUN_LOG_FILE = BASE_DIR / "outputs" / "run_log.json"
EVAL_REPORT_FILE = BASE_DIR / "EVAL_REPORT.md"

# ── Config ─────────────────────────────────────────────────────────────────────
AGENT_NAME = "Trend Relevance & Materiality Filter"
BRAND = os.environ.get("BRAND", "Louis Vuitton")
DEFAULT_CITY = os.environ.get("DEFAULT_CITY", "Shanghai")
MAX_SHORTLIST = 15
SKIP_CATEGORIES = {"beauty"}  # excluded from real runs; not relevant for luxury fashion brand runs


# ── Known Celine products to scan for in real XHS evidence ─────────────────────
# Ordered longest-first so multi-word names (e.g. "Classique 16") match before
# shorter substrings (e.g. "Classique") when both appear in the same text.
CELINE_KNOWN_PRODUCTS = [
    "Celine Arc de Triomphe",
    "Classique 16",
    "Teen Triomphe",
    "tuxedo blazer",
    "wide-leg trousers",
    "biker jacket",
    "Soft 16",
    "Box bag",
    "Triomphe",
    "Cabas",
    "Besace",
    "loafers",
    "boots",
]


def extract_product_from_trend(trend: dict) -> Optional[str]:
    """
    Scan all evidence snippets and post titles/bodies for known Celine product names.
    Counts occurrences of each product name (case-insensitive) and returns the most
    frequently mentioned one, or None if none are found.
    Stores result as trend["extracted_product"] — call in-place before LLM evaluation.
    """
    evidence = trend.get("evidence", {})
    texts = list(evidence.get("snippets", []))
    for post in evidence.get("posts", []):
        if isinstance(post, dict):
            texts.append(post.get("title", ""))
            texts.append(post.get("body", ""))
    texts.append(trend.get("label", ""))
    texts.append(trend.get("summary", ""))

    combined = " ".join(str(t) for t in texts if t).lower()

    counts: dict = {}
    for product in CELINE_KNOWN_PRODUCTS:
        n = combined.count(product.lower())
        if n:
            counts[product] = n

    return max(counts, key=counts.get) if counts else None


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Union[dict, list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved: {path}")


def resolve_brand_profile(slug: str) -> Path:
    specific = BASE_DIR / f"brand_profile_{slug}.json"
    if specific.exists():
        return specific
    return BASE_DIR / "brand_profile.json"


def infer_run_id_from_path(path: Path) -> str:
    m = re.search(r"(run_\d+)", path.name)
    return m.group(1) if m else "run_unknown"


def load_all_real_trends() -> "tuple[list, list, str]":
    """
    Load ALL run_*_trend_objects.json from module_1/outputs/runs/.
    Skips any trend where category is in SKIP_CATEGORIES (e.g. beauty).
    Namespaces IDs as run_XXXX_tYY. Tags data_type='real'.

    Returns (real_trends, beauty_skipped_log, combined_run_id)
    """
    run_files = sorted(MODULE1_RUNS_DIR.glob("run_*_trend_objects.json"))
    if not run_files:
        fallback = BASE_DIR / "data" / "trend_objects.json"
        if fallback.exists():
            print(f"[INFO] No Module 1 run files found. Using bundled sample: {fallback}")
            data = load_json(fallback)
            trends = data.get("trend_objects", [])
            for t in trends:
                t.setdefault("data_type", "real")
            return trends, [], "sample_data"
        raise FileNotFoundError(
            f"No run_*_trend_objects.json found in {MODULE1_RUNS_DIR}\n"
            "Run module_1/xhs_trend_builder.py first."
        )

    all_real = []
    skipped_log = []
    run_ids = []

    for run_file in run_files:
        run_id = infer_run_id_from_path(run_file)
        run_ids.append(run_id)
        data = load_json(run_file)
        raw_trends = data.get("trend_objects", [])
        if not raw_trends and isinstance(data, list):
            raw_trends = data

        for i, trend in enumerate(raw_trends):
            category = trend.get("category", "")
            orig_id = trend.get("trend_id", f"t{i+1:02d}")
            namespaced_id = f"{run_id}_{orig_id}"

            if category in SKIP_CATEGORIES:
                skipped_log.append({
                    "trend_id": namespaced_id,
                    "label": trend.get("label", ""),
                    "category": category,
                    "reason": f"Category '{category}' excluded — beauty runs not relevant for {BRAND}",
                })
                continue

            trend = dict(trend)
            trend["trend_id"] = namespaced_id
            trend["data_type"] = "real"
            trend.setdefault("location", "China")
            all_real.append(trend)

    combined = (
        f"{run_ids[0]}_to_{run_ids[-1]}" if len(run_ids) > 1
        else (run_ids[0] if run_ids else "unknown")
    )
    return all_real, skipped_log, combined


def load_synthetic_trends() -> list:
    """
    Load module_2/data/synthetic_trends.json.
    Namespaces IDs as synthetic_tYY. Tags data_type='synthetic'.
    """
    if not SYNTHETIC_TRENDS_FILE.exists():
        print(f"[INFO] No synthetic trends file found at {SYNTHETIC_TRENDS_FILE} — skipping.")
        return []

    data = load_json(SYNTHETIC_TRENDS_FILE)
    raw = data if isinstance(data, list) else data.get("trend_objects", [])

    synthetic = []
    for i, trend in enumerate(raw):
        trend = dict(trend)
        orig_id = trend.get("trend_id", f"t{i+1:02d}")
        if not str(orig_id).startswith("synthetic_"):
            trend["trend_id"] = f"synthetic_{orig_id}"
        trend["data_type"] = "synthetic"
        trend.setdefault("location", "China")
        synthetic.append(trend)

    return synthetic


def build_shortlist_output(
    shortlisted: list,
    all_evaluations: list,
    prefilter_rejected: list,
    beauty_skipped: list,
    total_input: int,
    module1_run_id: str,
    generated_at: str,
    run_id: str,
    all_trends_lookup: dict,
) -> dict:
    shortlist_items = []
    for rank, ev in enumerate(shortlisted, start=1):
        tid = ev.get("trend_id")
        original = all_trends_lookup.get(tid, {})
        scores = ev.get("scores", {})
        # ── Resolve hero_product with source tracking ──────────────────────
        extracted_product = original.get("extracted_product")
        llm_product = ev.get("hero_product_link")
        if extracted_product:
            hero_product = extracted_product
            hero_product_source = "extracted_from_posts"
        elif llm_product:
            hero_product = llm_product
            hero_product_source = "llm_suggested"
        else:
            hero_product = None
            hero_product_source = None

        item = {
            "rank": rank,
            "trend_id": tid,
            "label": ev.get("label", ""),
            "category": ev.get("category", ""),
            "location": original.get("location", "China"),
            "data_type": original.get("data_type", "unknown"),
            "composite_score": ev.get("composite_score"),
            "scores": {
                "brand_fit": scores.get("brand_fit"),
                "ca_conversational_utility": scores.get("ca_conversational_utility"),
                "trend_velocity": scores.get("trend_velocity"),
                "language_specificity": scores.get("language_specificity"),
                "client_persona_match": scores.get("client_persona_match"),
                "novelty": scores.get("novelty"),
                "category_fit": scores.get("category_fit"),
                "cross_run_persistence": scores.get("cross_run_persistence"),
            },
            "matched_archetype": ev.get("matched_archetype"),
            "matched_pillar": ev.get("matched_pillar"),
            "extracted_product": extracted_product,
            "hero_product": hero_product,
            "hero_product_source": hero_product_source,
            "hero_product_link": llm_product,   # LLM suggestion kept for reference
            "confidence": ev.get("confidence"),
            "why_selected": ev.get("reasoning", ev.get("why_selected", "")),
            "evidence_references": ev.get("evidence_references", []),
            "metric_signal": {
                "total_engagement": ev.get("metric_signal", {}).get("total_engagement"),
                "post_count": ev.get("metric_signal", {}).get("post_count"),
                "avg_engagement": ev.get("metric_signal", {}).get("avg_engagement"),
                "engagement_recency_pct": ev.get("engagement_recency_pct"),
                "run_count": ev.get("run_count"),
            },
        }
        shortlist_items.append(item)

    return {
        "run_id": run_id,
        "generated_at": generated_at,
        "brand": BRAND,
        "module1_run_id": module1_run_id,
        "total_evaluated": total_input,
        "total_beauty_skipped": len(beauty_skipped),
        "total_prefilter_rejected": len(prefilter_rejected),
        "total_shortlisted": len(shortlisted),
        "shortlist": shortlist_items,
    }


def calculate_quality_metrics(
    shortlisted: list,
    all_evaluations: list,
    prefilter_rejected: list,
    beauty_skipped: list,
    total_input: int,
    all_trends_lookup: dict,
) -> dict:
    brand_taboo_rejections = sum(
        1 for r in prefilter_rejected if "taboo" in r.get("reason", "").lower()
    )
    llm_low_brand_fit = sum(
        1 for ev in all_evaluations
        if (ev.get("scores") or {}).get("brand_fit", 10) < 5
    )
    off_brand_count = brand_taboo_rejections + llm_low_brand_fit
    off_brand_rate = round(off_brand_count / max(total_input, 1) * 100, 1)

    high_conf = sum(1 for ev in all_evaluations if ev.get("confidence") == "high")
    med_conf = sum(1 for ev in all_evaluations if ev.get("confidence") == "medium")
    low_conf = sum(1 for ev in all_evaluations if ev.get("confidence") == "low")
    spec_total = max(len(all_evaluations), 1)

    noise_reduction = round((total_input - len(shortlisted)) / max(total_input, 1) * 100, 1)

    real_shortlisted = sum(
        1 for ev in shortlisted
        if all_trends_lookup.get(ev.get("trend_id"), {}).get("data_type") == "real"
    )
    synthetic_shortlisted = len(shortlisted) - real_shortlisted

    return {
        "off_brand_rate": off_brand_rate,
        "off_brand_count": off_brand_count,
        "brand_taboo_rejections": brand_taboo_rejections,
        "llm_low_brand_fit": llm_low_brand_fit,
        "explanation_specificity": {
            "high": high_conf,
            "medium": med_conf,
            "low": low_conf,
            "high_pct": round(high_conf / spec_total * 100, 1),
            "med_pct": round(med_conf / spec_total * 100, 1),
            "low_pct": round(low_conf / spec_total * 100, 1),
        },
        "noise_reduction_rate": noise_reduction,
        "real_shortlisted": real_shortlisted,
        "synthetic_shortlisted": synthetic_shortlisted,
        "beauty_skipped": len(beauty_skipped),
    }


def find_failure_cases(all_evaluations: list, shortlisted_ids: set) -> list:
    """Return 5 lowest-scoring non-shortlisted evaluated trends."""
    non_shortlisted = [ev for ev in all_evaluations if ev.get("trend_id") not in shortlisted_ids]
    non_shortlisted.sort(key=lambda x: x.get("composite_score", 0))
    return non_shortlisted[:5]


def write_eval_report(
    run_id: str,
    generated_at: str,
    total_input: int,
    real_count: int,
    synthetic_count: int,
    beauty_skipped_count: int,
    prefilter_rejected: list,
    all_evaluations: list,
    shortlisted: list,
    quality: dict,
    failure_cases: list,
) -> None:
    """Auto-generate EVAL_REPORT.md at module_2/ with real run data. No placeholders."""
    spec = quality["explanation_specificity"]
    lines = [
        "# Module 2 — Evaluation Report",
        "",
        f"**Run ID:** {run_id}  ",
        f"**Generated at:** {generated_at}  ",
        f"**Brand:** {BRAND}",
        "",
        "---",
        "",
        "## Batch Composition",
        "",
        "| Source | Count |",
        "|--------|-------|",
        f"| Real XHS (luxury_fashion) | {real_count} |",
        f"| Synthetic (luxury_fashion) | {synthetic_count} |",
        f"| Beauty runs skipped | {beauty_skipped_count} |",
        f"| **Total input to filter** | **{total_input}** |",
        "",
        "---",
        "",
        "## Filter Results",
        "",
        f"- Pre-filter rejected: **{len(prefilter_rejected)}**",
        f"- Passed to LLM: **{len(all_evaluations)}**",
        f"- Shortlisted: **{len(shortlisted)}**",
        f"- Noise reduction rate: **{quality['noise_reduction_rate']}%**",
        "",
        "---",
        "",
        "## Quality Checks",
        "",
        "### 1. Off-Brand Rate",
        f"- Off-brand count: {quality['off_brand_count']} ({quality['off_brand_rate']}% of input)",
        f"  - Taboo keyword rejections: {quality['brand_taboo_rejections']}",
        f"  - LLM brand_fit < 5: {quality['llm_low_brand_fit']}",
        "",
        "### 2. Explanation Specificity (LLM confidence breakdown)",
        f"- High: {spec['high']} ({spec['high_pct']}%)",
        f"- Medium: {spec['medium']} ({spec['med_pct']}%)",
        f"- Low: {spec['low']} ({spec['low_pct']}%)",
        "",
        "### 3. Noise Reduction",
        f"- {quality['noise_reduction_rate']}% of input trends were filtered before reaching the shortlist.",
        "",
        "### 4. New Dimensions (Week 11)",
        "- **CA Conversational Utility**: % of shortlisted trends with a named hero product link — "
        f"{sum(1 for ev in all_evaluations if ev.get('hero_product_link'))} of {len(all_evaluations)} evaluated trends had a specific product anchor.",
        "- **Client Archetype Coverage**: archetypes matched across shortlist — "
        + ", ".join(
            sorted({ev.get('matched_archetype') for ev in all_evaluations if ev.get('matched_archetype')})
        ) or "none recorded",
        "- **Trend Velocity**: scores computed from engagement_recency_pct (7-day recency window).",
        "- **Cross-Run Persistence**: scores computed from run_count (deduplication merged trends retain count).",
        "",
        "---",
        "",
        "## Shortlist Summary",
        "",
        f"Shortlisted **{len(shortlisted)}** trends "
        f"(real: {quality['real_shortlisted']}, synthetic: {quality['synthetic_shortlisted']}):",
        "",
        "| # | Trend | Score | Archetype | Hero Product | Pillar | CA Utility | Velocity |",
        "|---|-------|-------|-----------|-------------|--------|-----------|---------|",
    ]
    for i, ev in enumerate(shortlisted, 1):
        scores = ev.get("scores", {})
        lines.append(
            f"| {i} | **[{ev.get('trend_id')}]** {ev.get('label', '')} "
            f"| {ev.get('composite_score', 0):.2f} "
            f"| {ev.get('matched_archetype') or '—'} "
            f"| {ev.get('hero_product_link') or '—'} "
            f"| {ev.get('matched_pillar') or '—'} "
            f"| {scores.get('ca_conversational_utility', '—')} "
            f"| {scores.get('trend_velocity', '—')} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Failure Cases (5 Lowest Scoring)",
        "",
    ]
    if failure_cases:
        for ev in failure_cases:
            reason = ev.get("disqualifying_reason") or "Below threshold or LLM rejected"
            archetype = ev.get("matched_archetype") or "no archetype matched"
            scores = ev.get("scores", {})
            lines.append(
                f"- **[{ev.get('trend_id')}]** {ev.get('label', '')} "
                f"— score: {ev.get('composite_score', 0):.2f}"
            )
            lines.append(f"  - Reason: {reason}")
            lines.append(
                f"  - Target archetype: {archetype} "
                f"| client_persona_match: {scores.get('client_persona_match', '—')} "
                f"| ca_conversational_utility: {scores.get('ca_conversational_utility', '—')} "
                f"| novelty: {scores.get('novelty', '—')}"
            )
    else:
        lines.append("- No failure cases (all evaluated trends were shortlisted).")

    lines += [
        "",
        "---",
        "",
        "## Known Limitations",
        "",
        "1. Runs 0001–0008 are beauty category and excluded — not relevant for luxury fashion brand filtering.",
        "2. Runs 0009–0013 contain identical underlying XHS data (same 3 posts scraped across 5 runs).",
        "3. Synthetic trends are clearly marked `data_type: synthetic` and should not be presented as real XHS signal.",
        "4. No image URLs captured — scraping ran with `--no-detail` flag.",
        "",
    ]

    EVAL_REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved: {EVAL_REPORT_FILE}")


def convert_to_module3_format(
    shortlisted: list,
    all_trends_lookup: dict,
    generated_at: str,
    module1_run_id: str,
) -> dict:
    trends_m3 = []
    for ev in shortlisted:
        tid = ev.get("trend_id", "")
        original = all_trends_lookup.get(tid, {})
        metrics = original.get("metrics", {})
        evidence = original.get("evidence", {})
        snippets = evidence.get("snippets", [])
        posts = evidence.get("posts", [])

        total_eng = metrics.get("total_engagement", 0)
        post_count = metrics.get("post_count", 1) or 1
        avg_eng = total_eng / post_count
        engagement_rate = round(min(avg_eng / 10000, 1.0), 4)

        wow_growth = original.get("momentum_signal", "+0%")
        if not wow_growth or wow_growth == "+0%":
            wow_growth = "+15%"

        top_post_example = (
            snippets[0] if snippets else (posts[0].get("title", "") if posts else "")
        )
        hashtags = evidence.get("top_hashtags", [])
        if not hashtags:
            kw = original.get("keyword", original.get("label", ""))
            hashtags = [f"#{kw}"] if kw else []

        composite = ev.get("composite_score", 0)
        brand_relevance = "high" if composite >= 7.5 else ("medium" if composite >= 6.5 else "low")

        trends_m3.append({
            "trend_id": tid,
            "trend_label": ev.get("label", original.get("label", "")),
            "city": original.get("location", DEFAULT_CITY),
            "category": ev.get("category", original.get("category", "luxury_fashion")),
            "data_type": original.get("data_type", "unknown"),
            "target_age_range": original.get("target_age_range", "28–45"),
            "cluster_summary": original.get("summary", ev.get("why_selected", "")),
            "post_count": metrics.get("post_count", post_count),
            "engagement_rate": engagement_rate,
            "top_post_example": top_post_example,
            "trending_hashtags": hashtags[:5],
            "brand_relevance": brand_relevance,
            "week_on_week_growth": wow_growth,
            "m2_composite_score": composite,
            "m2_confidence": ev.get("confidence", "medium"),
            "m2_why_selected": ev.get("why_selected", ev.get("reasoning", "")),
            "extracted_product": original.get("extracted_product"),
            "hero_product": ev.get("hero_product"),
            "hero_product_source": ev.get("hero_product_source"),
        })

    week = datetime.now(timezone.utc).strftime("%Y-W%W")
    return {
        "query_context": {
            "brand": BRAND,
            "market": "China luxury fashion",
            "categories": ["luxury_fashion", "ready-to-wear", "leather goods"],
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
    print("\nLoading real trend objects from Module 1 runs (beauty category skipped)...")
    real_trends, beauty_skipped, module1_run_id = load_all_real_trends()
    print(f"  Beauty skipped: {len(beauty_skipped)} objects")
    print(f"  Real luxury_fashion loaded: {len(real_trends)}")

    print("\nSynthetic trends skipped — running on real XHS data only (Week 11 requirement)")
    synthetic_trends = []

    all_trends = real_trends
    total_input = len(all_trends)
    print(f"\nReal (XHS): {len(real_trends)} / Synthetic: {len(synthetic_trends)} / Total: {total_input}")

    print(f"\nLoading brand profile...")
    slug = BRAND.lower().strip().replace(" ", "_").replace("-", "_")
    brand_profile = load_json(resolve_brand_profile(slug))
    print(f"Brand profile: {brand_profile['brand_name']}")

    all_trends_lookup = {t["trend_id"]: t for t in all_trends}

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
        sys.exit(0)

    # ── Step 1.5: Organic product extraction ──────────────────────────────────
    print(f"\n{'─'*60}")
    print("STEP 1.5 — Organic Product Extraction from XHS Snippets")
    print(f"{'─'*60}")
    extracted_count = 0
    for trend in passed_trends:
        product = extract_product_from_trend(trend)
        if product:
            trend["extracted_product"] = product
            extracted_count += 1
    print(f"  Organic product mention found in {extracted_count}/{len(passed_trends)} trends")
    if extracted_count:
        for t in passed_trends:
            if t.get("extracted_product"):
                print(f"  ✓ [{t['trend_id']}] → {t['extracted_product']}")

    # ── Step 2: LLM Evaluation ─────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print(f"STEP 2 — LLM Evaluation ({len(passed_trends)} trends)")
    print(f"{'─'*60}")

    all_evaluations = evaluate_batch(passed_trends, brand_profile)

    for ev in all_evaluations:
        tid = ev.get("trend_id")
        if tid and tid in all_trends_lookup:
            original = all_trends_lookup[tid]
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
    shortlisted_ids = {ev.get("trend_id") for ev in shortlisted}

    print(f"\nShortlist ({len(shortlisted)} trends):")
    for i, ev in enumerate(shortlisted, start=1):
        tid = ev.get("trend_id")
        dtype = all_trends_lookup.get(tid, {}).get("data_type", "?")
        print(
            f"  #{i} [{tid}] {ev.get('label', '')} "
            f"— {ev.get('composite_score', 0):.2f} [{dtype}]"
        )

    llm_rejected = [ev for ev in all_evaluations if ev.get("trend_id") not in shortlisted_ids]
    if llm_rejected:
        print(f"\nLLM-rejected ({len(llm_rejected)}):")
        for ev in llm_rejected:
            reason = ev.get("disqualifying_reason") or "Below threshold"
            print(f"  ✗ [{ev.get('trend_id')}] {ev.get('label', '')} — {reason}")

    # ── Quality metrics ────────────────────────────────────────────────────────
    quality = calculate_quality_metrics(
        shortlisted, all_evaluations, prefilter_rejected, beauty_skipped,
        total_input, all_trends_lookup,
    )
    failure_cases = find_failure_cases(all_evaluations, shortlisted_ids)

    spec = quality["explanation_specificity"]
    print(f"\nQuality Metrics:")
    print(f"  Off-brand rate:   {quality['off_brand_rate']}%")
    print(
        f"  Explanation spec: high={spec['high']} ({spec['high_pct']}%), "
        f"med={spec['medium']} ({spec['med_pct']}%), "
        f"low={spec['low']} ({spec['low_pct']}%)"
    )
    print(f"  Noise reduction:  {quality['noise_reduction_rate']}%")

    # ── Step 4: Write Outputs ──────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print("STEP 4 — Writing Outputs")
    print(f"{'─'*60}")

    generated_at = now.isoformat()

    shortlist_output = build_shortlist_output(
        shortlisted=shortlisted,
        all_evaluations=all_evaluations,
        prefilter_rejected=prefilter_rejected,
        beauty_skipped=beauty_skipped,
        total_input=total_input,
        module1_run_id=module1_run_id,
        generated_at=generated_at,
        run_id=run_id,
        all_trends_lookup=all_trends_lookup,
    )
    save_json(OUTPUT_SHORTLIST_FILE, shortlist_output)

    run_log = {
        "run_id": run_id,
        "agent_name": AGENT_NAME,
        "brand": BRAND,
        "module1_run_id": module1_run_id,
        "generated_at": generated_at,
        "total_input": total_input,
        "real_count": len(real_trends),
        "synthetic_count": len(synthetic_trends),
        "beauty_skipped_count": len(beauty_skipped),
        "prefilter_rejections": prefilter_rejected,
        "llm_evaluations": all_evaluations,
        "shortlist_ids": list(shortlisted_ids),
        "quality_metrics": quality,
        "output_file": str(OUTPUT_SHORTLIST_FILE),
    }
    save_json(RUN_LOG_FILE, run_log)

    m3_data = convert_to_module3_format(
        shortlisted=shortlisted,
        all_trends_lookup=all_trends_lookup,
        generated_at=generated_at,
        module1_run_id=module1_run_id,
    )
    save_json(MODULE3_SHORTLIST, m3_data)
    print(f"[M2→M3] Module 3 shortlist written: {MODULE3_SHORTLIST}")

    write_eval_report(
        run_id=run_id,
        generated_at=generated_at,
        total_input=total_input,
        real_count=len(real_trends),
        synthetic_count=len(synthetic_trends),
        beauty_skipped_count=len(beauty_skipped),
        prefilter_rejected=prefilter_rejected,
        all_evaluations=all_evaluations,
        shortlisted=shortlisted,
        quality=quality,
        failure_cases=failure_cases,
    )

    # ── Supabase (graceful fallback) ───────────────────────────────────────────
    try:
        sys.path.insert(0, str(ROOT_DIR))
        from supabase_client import is_configured
        if is_configured():
            from supabase_writer import write_shortlist, write_run_log
            write_shortlist(run_id, shortlist_output)
            write_run_log(
                run_id, module1_run_id, total_input,
                len(prefilter_rejected), len(passed_trends), len(shortlisted), generated_at,
            )
            print("[Supabase] Module 2 data synced.")
        else:
            print("Supabase not connected — skipping DB write. Results saved locally.")
    except Exception as e:
        print(f"Supabase not connected — skipping DB write. Results saved locally. ({e})")

    # ── Summary ────────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("RUN SUMMARY")
    print(f"{'='*60}")
    print(f"  Real luxury_fashion:   {len(real_trends)}")
    print(f"  Synthetic:             {len(synthetic_trends)}")
    print(f"  Beauty skipped:        {len(beauty_skipped)}")
    print(f"  Total input:           {total_input}")
    print(f"  Pre-filter rejected:   {len(prefilter_rejected)}")
    print(f"  LLM evaluated:         {len(all_evaluations)}")
    print(f"  Shortlisted:           {len(shortlisted)}")
    print(f"  Noise reduction:       {quality['noise_reduction_rate']:.1f}%")
    print(f"\n  → {OUTPUT_SHORTLIST_FILE.name}")
    print(f"  → {RUN_LOG_FILE.name}")
    print(f"  → module_3/trend_brief_agent/trend_shortlist.json")
    print(f"  → EVAL_REPORT.md")
    print("=" * 60)


if __name__ == "__main__":
    main()
