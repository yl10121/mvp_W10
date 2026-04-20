"""
batch_runner.py — Run Module 2 pipeline across multiple weekly-window batches.

Splits 40 Module 1 run files into 7 batches (batch 1 = beauty, skipped).
For each active batch: runs full pipeline (dedup → recency → pre-filter →
product extraction → LLM evaluation → shortlisting → Supabase write).

Outputs:
  module_2/outputs/batch_summary.json  — per-batch + aggregate metrics
  module_2/BATCH_SUMMARY.md            — human-readable markdown summary

Usage:
    cd /Users/kellyliu/Desktop/mvp_W10
    python module_2/batch_runner.py
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

_ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

_key_preview = os.environ.get("OPENROUTER_API_KEY", "")[:8] or "(not set)"
print(f"[ENV] OPENROUTER_API_KEY loaded: {_key_preview}...")

# ── Path setup ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
ROOT_DIR = BASE_DIR.parent
sys.path.insert(0, str(BASE_DIR))       # scorer, evaluator, agent, supabase_writer
sys.path.insert(0, str(ROOT_DIR))       # supabase_client

MODULE1_RUNS_DIR = ROOT_DIR / "module_1" / "outputs" / "runs"
OUTPUT_DIR = BASE_DIR / "outputs"
BATCH_SUMMARY_JSON = OUTPUT_DIR / "batch_summary.json"
BATCH_SUMMARY_MD = BASE_DIR / "BATCH_SUMMARY.md"

# ── Import pipeline components ──────────────────────────────────────────────────
from scorer import run_prefilter_batch
from evaluator import evaluate_batch, select_shortlist
from agent import (
    BRAND,
    SKIP_CATEGORIES,
    MAX_SHORTLIST,
    KNOWN_PRODUCTS,
    extract_product_from_trend,
    detect_signals,
    find_best_evidence_quote,
    build_shortlist_output,
    calculate_quality_metrics,
    find_failure_cases,
    resolve_brand_profile,
    load_json,
    save_json,
)

# ── Batch definitions ───────────────────────────────────────────────────────────
# run_range is (lo, hi) inclusive, matching the zero-padded run number in filenames.
BATCHES = [
    {"id": 1, "label": "Beauty runs (0001–0008)",  "run_range": (1,  8),  "skip": True},
    {"id": 2, "label": "Week A: runs 0009–0013",   "run_range": (9,  13), "skip": False},
    {"id": 3, "label": "Week B: runs 0014–0018",   "run_range": (14, 18), "skip": False},
    {"id": 4, "label": "Week C: runs 0019–0023",   "run_range": (19, 23), "skip": False},
    {"id": 5, "label": "Week D: runs 0024–0028",   "run_range": (24, 28), "skip": False},
    {"id": 6, "label": "Week E: runs 0029–0033",   "run_range": (29, 33), "skip": False},
    {"id": 7, "label": "Week F: runs 0034–0040",   "run_range": (34, 40), "skip": False},
]


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _run_number(path: Path) -> Optional[int]:
    m = re.search(r"run_(\d+)_", path.name)
    return int(m.group(1)) if m else None


def load_trends_for_batch(run_range: tuple) -> "tuple[list, list, list]":
    """
    Load trend objects from run files whose number falls in run_range (inclusive).
    Skips SKIP_CATEGORIES (beauty). Namespaces IDs as run_XXXX_tYY.

    Returns: (trends, beauty_skipped_log, run_ids_used)
    """
    lo, hi = run_range
    all_files = sorted(MODULE1_RUNS_DIR.glob("run_*_trend_objects.json"))
    batch_files = [f for f in all_files if lo <= (_run_number(f) or -1) <= hi]

    trends, beauty_skipped, run_ids = [], [], []

    for run_file in batch_files:
        rnum = _run_number(run_file)
        run_label = f"run_{rnum:04d}"
        run_ids.append(run_label)

        data = load_json(run_file)
        raw = data.get("trend_objects", [])
        if not raw and isinstance(data, list):
            raw = data

        for i, trend in enumerate(raw):
            category = trend.get("category", "")
            orig_id = trend.get("trend_id", f"t{i+1:02d}")
            nsid = f"{run_label}_{orig_id}"

            if category in SKIP_CATEGORIES:
                beauty_skipped.append({"trend_id": nsid, "category": category})
                continue

            trend = dict(trend)
            trend["trend_id"] = nsid
            trend["data_type"] = "real"
            trend.setdefault("location", "China")
            trends.append(trend)

    return trends, beauty_skipped, run_ids


def _categorise_rejection(reason: str) -> str:
    r = (reason or "").lower()
    if "staleness" in r or "before staleness" in r:
        return "staleness"
    if "brand signal" in r:
        return "low_brand_signal"
    if "post_count" in r:
        return "low_post_count"
    if "snippet" in r:
        return "low_snippets"
    if "taboo" in r:
        return "taboo_keyword"
    if "active_categories" in r:
        return "category_mismatch"
    return "other"


# ── Single batch runner ─────────────────────────────────────────────────────────

def run_batch(batch_def: dict, brand_profile: dict) -> dict:
    """Run the full Module 2 pipeline for one batch. Returns a result dict."""
    batch_id = batch_def["id"]
    label = batch_def["label"]
    run_range = batch_def["run_range"]

    print(f"\n{'='*60}")
    print(f"BATCH {batch_id}: {label}")
    print(f"{'='*60}")

    # Load trends for this batch
    all_trends, beauty_skipped, run_ids = load_trends_for_batch(run_range)
    total_input = len(all_trends)

    now = datetime.now(timezone.utc)
    run_id = f"m2_b{batch_id:02d}_{now.strftime('%Y%m%d_%H%M%S')}"
    generated_at = now.isoformat()
    module1_run_id = "_".join(run_ids) if run_ids else "none"

    print(f"  Run ID:         {run_id}")
    print(f"  Run files:      {len(run_ids)} ({run_ids[0] if run_ids else 'none'} … {run_ids[-1] if len(run_ids) > 1 else ''})")
    print(f"  Trend objects:  {total_input}")
    print(f"  Beauty skipped: {len(beauty_skipped)}")

    if total_input == 0:
        print("  No trends to process — batch empty.")
        return {
            "batch_id": batch_id, "label": label, "run_id": run_id,
            "run_range": list(run_range), "run_files": run_ids,
            "total_input": 0, "beauty_skipped": len(beauty_skipped),
            "prefilter_rejected": 0, "llm_evaluated": 0, "shortlisted": 0,
            "noise_reduction_rate": 0.0, "off_brand_rate": 0.0,
            "shortlisted_items": [], "prefilter_rejected_log": [], "quality": {},
        }

    all_trends_lookup = {t["trend_id"]: t for t in all_trends}

    # Step 1.5 — Organic product extraction + signal detection
    print("\n  [Step 1.5] Organic product extraction & signal detection...")
    extracted_count = 0
    celebrity_count = 0
    occasion_count = 0
    competitor_count = 0
    for trend in all_trends:
        product = extract_product_from_trend(trend)
        if product:
            trend["extracted_product"] = product
            extracted_count += 1
        detect_signals(trend)
        if trend.get("celebrity_signal"):
            celebrity_count += 1
        if trend.get("occasion_signal"):
            occasion_count += 1
        if trend.get("competitor_signal"):
            competitor_count += 1
    print(f"  → Product mention: {extracted_count}/{total_input} | Celebrity: {celebrity_count} | Occasion: {occasion_count} | Competitor: {competitor_count}")

    # Step 1 — Pre-filter
    print("\n  [Step 1] Pre-filter...")
    passed_trends, prefilter_rejected = run_prefilter_batch(all_trends, brand_profile)
    print(f"  → Passed: {len(passed_trends)} | Rejected: {len(prefilter_rejected)}")

    if not passed_trends:
        print("  No trends passed pre-filter — skipping LLM evaluation.")
        return {
            "batch_id": batch_id, "label": label, "run_id": run_id,
            "run_range": list(run_range), "run_files": run_ids,
            "total_input": total_input, "beauty_skipped": len(beauty_skipped),
            "prefilter_rejected": len(prefilter_rejected), "llm_evaluated": 0,
            "shortlisted": 0, "noise_reduction_rate": 100.0, "off_brand_rate": 0.0,
            "shortlisted_items": [], "prefilter_rejected_log": prefilter_rejected,
            "quality": {"noise_reduction_rate": 100.0, "off_brand_count": 0,
                        "off_brand_rate": 0.0, "brand_taboo_rejections": 0,
                        "llm_low_brand_fit": 0},
        }

    # Step 2 — LLM evaluation
    print(f"\n  [Step 2] LLM evaluation ({len(passed_trends)} trends)...")
    all_evaluations = evaluate_batch(passed_trends, brand_profile)

    for ev in all_evaluations:
        tid = ev.get("trend_id")
        if tid and tid in all_trends_lookup:
            orig = all_trends_lookup[tid]
            ev["label"] = orig.get("label", "")
            ev["category"] = orig.get("category", "")
            metrics = orig.get("metrics", {})
            ev["metric_signal"] = {
                "total_engagement": metrics.get("total_engagement"),
                "post_count": metrics.get("post_count"),
                "avg_engagement": metrics.get("avg_engagement"),
            }

    print(f"  → Evaluated: {len(all_evaluations)} trends")

    # Step 3 — Shortlist selection
    shortlisted = select_shortlist(all_evaluations, max_shortlist=MAX_SHORTLIST)
    shortlisted_ids = {ev.get("trend_id") for ev in shortlisted}
    print(f"  → Shortlisted: {len(shortlisted)} trends")

    for i, ev in enumerate(shortlisted, 1):
        print(
            f"     #{i} [{ev.get('trend_id')}] {ev.get('label', '')} "
            f"— {ev.get('composite_score', 0):.2f}"
        )

    # Best evidence quote per shortlisted trend
    for ev in shortlisted:
        tid = ev.get("trend_id")
        original = all_trends_lookup.get(tid, {})
        ev["best_evidence_quote"] = find_best_evidence_quote(original)

    # Quality metrics & shortlist output
    quality = calculate_quality_metrics(
        shortlisted, all_evaluations, prefilter_rejected,
        beauty_skipped, total_input, all_trends_lookup,
    )

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

    # Supabase write
    try:
        from supabase_client import is_configured
        if is_configured():
            from supabase_writer import write_shortlist, write_run_log
            write_shortlist(run_id, shortlist_output)
            write_run_log(
                run_id, module1_run_id, total_input,
                len(prefilter_rejected), len(passed_trends),
                len(shortlisted), generated_at,
            )
            print(f"  [Supabase] Batch {batch_id} synced.")
        else:
            print("  [Supabase] Not configured — skipping DB write.")
    except Exception as e:
        print(f"  [Supabase] Skipped — {e}")

    return {
        "batch_id": batch_id,
        "label": label,
        "run_id": run_id,
        "run_range": list(run_range),
        "run_files": run_ids,
        "total_input": total_input,
        "beauty_skipped": len(beauty_skipped),
        "prefilter_rejected": len(prefilter_rejected),
        "llm_evaluated": len(all_evaluations),
        "shortlisted": len(shortlisted),
        "noise_reduction_rate": quality["noise_reduction_rate"],
        "off_brand_rate": quality["off_brand_rate"],
        "shortlisted_items": shortlist_output.get("shortlist", []),
        "prefilter_rejected_log": prefilter_rejected,
        "quality": quality,
        "signal_counts": {
            "celebrity": celebrity_count,
            "occasion": occasion_count,
            "competitor": competitor_count,
        },
    }


# ── Aggregate metrics ───────────────────────────────────────────────────────────

def compute_aggregate_metrics(batch_results: list) -> dict:
    """Compute cross-batch aggregate metrics from all completed batch result dicts."""
    all_items = []
    all_rejected = []
    for b in batch_results:
        all_items.extend(b.get("shortlisted_items", []))
        all_rejected.extend(b.get("prefilter_rejected_log", []))

    total_files = sum(len(b.get("run_files", [])) for b in batch_results)
    total_input = sum(b.get("total_input", 0) for b in batch_results)
    total_shortlisted = sum(b.get("shortlisted", 0) for b in batch_results)
    total_evaluated = sum(b.get("llm_evaluated", 0) for b in batch_results)

    # Shortlist and noise rates (exclude batches with no input)
    active = [b for b in batch_results if b.get("total_input", 0) > 0]
    noise_rates = [b["noise_reduction_rate"] for b in active]
    shortlist_rates = [
        b["shortlisted"] / b["total_input"] * 100
        for b in active
    ]

    avg_shortlist_rate = round(sum(shortlist_rates) / len(shortlist_rates), 1) if shortlist_rates else 0
    avg_noise_reduction = round(sum(noise_rates) / len(noise_rates), 1) if noise_rates else 0
    noise_range = {
        "min": round(min(noise_rates), 1),
        "max": round(max(noise_rates), 1),
    } if noise_rates else {"min": 0.0, "max": 0.0}

    # Off-brand rate
    total_off_brand = sum(b.get("quality", {}).get("off_brand_count", 0) for b in batch_results)
    overall_off_brand_rate = round(total_off_brand / max(total_input, 1) * 100, 1)

    # % shortlisted with extracted product anchor
    extracted_count = sum(
        1 for item in all_items
        if item.get("hero_product_source") == "extracted_from_posts"
    )
    pct_extracted = round(extracted_count / max(total_shortlisted, 1) * 100, 1)

    # Rejection reason breakdown (prefilter only)
    rejection_cats: dict = {}
    for r in all_rejected:
        cat = _categorise_rejection(r.get("reason", ""))
        rejection_cats[cat] = rejection_cats.get(cat, 0) + 1
    total_rejected = sum(rejection_cats.values())
    rejection_pct = {
        k: round(v / max(total_rejected, 1) * 100, 1)
        for k, v in sorted(rejection_cats.items(), key=lambda x: -x[1])
        if v > 0
    }

    # Subcategory distribution — infer from item if not stored
    try:
        from supabase_writer import _infer_subcategory
        def _get_subcat(item):
            return _infer_subcategory(
                item.get("label", ""),
                item.get("hero_product", ""),
                item.get("why_selected", ""),
            )
    except ImportError:
        def _get_subcat(item):
            return item.get("subcategory", "general_aesthetic")

    subcat_counts: dict = {}
    for item in all_items:
        sc = _get_subcat(item)
        subcat_counts[sc] = subcat_counts.get(sc, 0) + 1
    subcat_pct = {
        k: round(v / max(total_shortlisted, 1) * 100, 1)
        for k, v in sorted(subcat_counts.items(), key=lambda x: -x[1])
    }

    # Signal rates across all batches
    total_celebrity = sum(b.get("signal_counts", {}).get("celebrity", 0) for b in batch_results)
    total_occasion = sum(b.get("signal_counts", {}).get("occasion", 0) for b in batch_results)
    total_competitor = sum(b.get("signal_counts", {}).get("competitor", 0) for b in batch_results)
    signal_base = max(total_input, 1)

    # CWC vs raw composite comparison across all shortlisted items
    cwc_scores = [item.get("confidence_weighted_composite") for item in all_items if item.get("confidence_weighted_composite") is not None]
    raw_scores = [item.get("raw_composite_score") for item in all_items if item.get("raw_composite_score") is not None]
    avg_cwc = round(sum(cwc_scores) / len(cwc_scores), 2) if cwc_scores else 0.0
    avg_raw = round(sum(raw_scores) / len(raw_scores), 2) if raw_scores else 0.0

    return {
        "total_run_files_processed": total_files,
        "total_trend_objects_processed": total_input,
        "total_llm_evaluated": total_evaluated,
        "total_shortlisted": total_shortlisted,
        "avg_shortlist_rate_pct": avg_shortlist_rate,
        "avg_noise_reduction_rate_pct": avg_noise_reduction,
        "noise_reduction_range_pct": noise_range,
        "overall_off_brand_rate_pct": overall_off_brand_rate,
        "pct_shortlisted_with_extracted_product": pct_extracted,
        "rejection_reason_breakdown_pct": rejection_pct,
        "rejection_reason_counts": rejection_cats,
        "total_prefilter_rejected": total_rejected,
        "subcategory_distribution_pct": subcat_pct,
        "signal_rates": {
            "celebrity_count": total_celebrity,
            "celebrity_rate_pct": round(total_celebrity / signal_base * 100, 1),
            "occasion_count": total_occasion,
            "occasion_rate_pct": round(total_occasion / signal_base * 100, 1),
            "competitor_count": total_competitor,
            "competitor_rate_pct": round(total_competitor / signal_base * 100, 1),
        },
        "scoring": {
            "avg_confidence_weighted_composite": avg_cwc,
            "avg_raw_composite": avg_raw,
            "avg_confidence_discount": round(avg_raw - avg_cwc, 2),
        },
    }


# ── Markdown summary writer ─────────────────────────────────────────────────────

def write_batch_summary_md(batch_results: list, agg: dict) -> None:
    lines = [
        "# Module 2 — Batch Summary",
        "",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}  ",
        f"**Brand:** {BRAND}  ",
        f"**Batches run:** {len(batch_results)} (of 7 defined; batch 1 beauty skipped)",
        "",
        "---",
        "",
        "## Aggregate Metrics",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total run files processed | {agg['total_run_files_processed']} |",
        f"| Total trend objects processed | {agg['total_trend_objects_processed']} |",
        f"| Total LLM evaluated | {agg['total_llm_evaluated']} |",
        f"| Total shortlisted | {agg['total_shortlisted']} |",
        f"| Average shortlist rate | {agg['avg_shortlist_rate_pct']}% |",
        f"| Average noise reduction rate | {agg['avg_noise_reduction_rate_pct']}% |",
        f"| Noise reduction range | {agg['noise_reduction_range_pct']['min']}% – {agg['noise_reduction_range_pct']['max']}% |",
        f"| Overall off-brand rate | {agg['overall_off_brand_rate_pct']}% |",
        f"| % shortlisted with extracted product anchor | {agg['pct_shortlisted_with_extracted_product']}% |",
        f"| Celebrity signal rate | {agg.get('signal_rates', {}).get('celebrity_rate_pct', 0)}% ({agg.get('signal_rates', {}).get('celebrity_count', 0)} trends) |",
        f"| Occasion signal rate | {agg.get('signal_rates', {}).get('occasion_rate_pct', 0)}% ({agg.get('signal_rates', {}).get('occasion_count', 0)} trends) |",
        f"| Competitor signal rate | {agg.get('signal_rates', {}).get('competitor_rate_pct', 0)}% ({agg.get('signal_rates', {}).get('competitor_count', 0)} trends) |",
        f"| Avg raw composite (shortlisted) | {agg.get('scoring', {}).get('avg_raw_composite', 0)} |",
        f"| Avg CWC (after confidence weighting) | {agg.get('scoring', {}).get('avg_confidence_weighted_composite', 0)} |",
        f"| Avg confidence discount | -{agg.get('scoring', {}).get('avg_confidence_discount', 0)} |",
        "",
        "---",
        "",
        "## Per-Batch Results",
        "",
        "| Batch | Label | Input | Pre-filter rejected | LLM evaluated | Shortlisted | Noise reduction |",
        "|-------|-------|-------|--------------------:|:-------------:|:-----------:|:--------------:|",
    ]
    for b in batch_results:
        lines.append(
            f"| {b['batch_id']} | {b['label']} | {b['total_input']} "
            f"| {b['prefilter_rejected']} | {b['llm_evaluated']} "
            f"| {b['shortlisted']} | {b['noise_reduction_rate']}% |"
        )

    lines += [
        "",
        "---",
        "",
        "## Rejection Reason Breakdown (pre-filter)",
        "",
        "| Reason | Count | % of all rejected |",
        "|--------|------:|------------------:|",
    ]
    counts = agg.get("rejection_reason_counts", {})
    pcts = agg.get("rejection_reason_breakdown_pct", {})
    for reason, pct in pcts.items():
        lines.append(f"| {reason} | {counts.get(reason, 0)} | {pct}% |")

    lines += [
        "",
        "---",
        "",
        "## Subcategory Distribution (shortlisted trends)",
        "",
        "| Subcategory | % of shortlisted |",
        "|-------------|:----------------:|",
    ]
    for sc, pct in agg.get("subcategory_distribution_pct", {}).items():
        lines.append(f"| {sc} | {pct}% |")

    lines += [
        "",
        "---",
        "",
        "## Shortlisted Trends — All Batches",
        "",
        "| Batch | Trend ID | Label | Score | Extracted Product | Source |",
        "|-------|----------|-------|------:|------------------|--------|",
    ]
    for b in batch_results:
        for item in b.get("shortlisted_items", []):
            lines.append(
                f"| {b['batch_id']} "
                f"| {item.get('trend_id', '')} "
                f"| {(item.get('label', '') or '')[:50]} "
                f"| {item.get('composite_score', 0):.2f} "
                f"| {item.get('hero_product') or '—'} "
                f"| {item.get('hero_product_source') or '—'} |"
            )

    lines.append("")
    BATCH_SUMMARY_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nSaved: {BATCH_SUMMARY_MD}")


# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print(f"Module 2 Batch Runner")
    print(f"Brand: {BRAND}")
    print(f"Batches: {len(BATCHES)} defined ({sum(1 for b in BATCHES if not b['skip'])} active)")
    print("=" * 60)

    # Load brand profile (Atypica with static fallback)
    try:
        from atypica_client import get_or_refresh_brand_data
        brand_profile = get_or_refresh_brand_data(BRAND)
        brand_profile.pop("_source", None)
    except Exception as e:
        print(f"[Atypica] Not available ({e}) — using static JSON")
        slug = BRAND.lower().strip().replace(" ", "_").replace("-", "_").split("&")[0].strip().rstrip("_")
        brand_profile = load_json(resolve_brand_profile(slug))
    print(f"\nBrand: {brand_profile['brand_name']} ({len(brand_profile.get('client_archetypes', []))} archetypes)")

    batch_results = []

    for batch_def in BATCHES:
        if batch_def["skip"]:
            print(
                f"\n{'─'*60}\n"
                f"Batch {batch_def['id']}: {batch_def['label']} — SKIPPED "
                f"(beauty category; not relevant for {BRAND})\n"
                f"{'─'*60}"
            )
            continue

        result = run_batch(batch_def, brand_profile)
        batch_results.append(result)

    # Aggregate and write outputs
    print(f"\n{'='*60}")
    print("Computing aggregate metrics across all batches...")
    agg = compute_aggregate_metrics(batch_results)

    # Save JSON
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "brand": BRAND,
        "aggregate": agg,
        "batches": [
            {k: v for k, v in b.items() if k not in ("shortlisted_items", "prefilter_rejected_log", "quality")}
            for b in batch_results
        ],
    }
    with open(BATCH_SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary_payload, f, ensure_ascii=False, indent=2)
    print(f"Saved: {BATCH_SUMMARY_JSON}")

    write_batch_summary_md(batch_results, agg)

    # Print summary
    print(f"\n{'='*60}")
    print("BATCH RUN COMPLETE")
    print(f"{'='*60}")
    print(f"  Run files processed:      {agg['total_run_files_processed']}")
    print(f"  Trend objects processed:  {agg['total_trend_objects_processed']}")
    print(f"  Total shortlisted:        {agg['total_shortlisted']}")
    print(f"  Avg shortlist rate:       {agg['avg_shortlist_rate_pct']}%")
    print(f"  Avg noise reduction:      {agg['avg_noise_reduction_rate_pct']}%")
    print(f"  Noise reduction range:    {agg['noise_reduction_range_pct']['min']}% – {agg['noise_reduction_range_pct']['max']}%")
    print(f"  Off-brand rate:           {agg['overall_off_brand_rate_pct']}%")
    print(f"  Extracted product anchor: {agg['pct_shortlisted_with_extracted_product']}% of shortlisted")
    sr = agg.get("signal_rates", {})
    sc = agg.get("scoring", {})
    print(f"  Celebrity signal rate:    {sr.get('celebrity_rate_pct', 0)}%")
    print(f"  Occasion signal rate:     {sr.get('occasion_rate_pct', 0)}%")
    print(f"  Competitor signal rate:   {sr.get('competitor_rate_pct', 0)}%")
    print(f"  Avg raw composite:        {sc.get('avg_raw_composite', 0)}")
    print(f"  Avg CWC:                  {sc.get('avg_confidence_weighted_composite', 0)}")
    print()
    print(f"  → {BATCH_SUMMARY_JSON.name}")
    print(f"  → {BATCH_SUMMARY_MD.name}")
    print("=" * 60)


if __name__ == "__main__":
    main()
