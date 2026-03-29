#!/usr/bin/env python3
"""Evaluation harness for Module 1: XHS Trend Object Builder.

Reads the latest trend_objects.json from outputs/runs/, runs three quality
checks (duplication, evidence sufficiency, label clarity), prints a summary
to stdout, writes structured results to eval_results.json, and generates
EVAL_REPORT.md with pass/fail details and actionable recommendations.

Usage:
    python3 eval_harness.py
    python3 eval_harness.py --run run_0013
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
RUNS_DIR = SCRIPT_DIR / "outputs" / "runs"
OUTPUT_DIR = SCRIPT_DIR / "outputs"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_latest_run(runs_dir: Path, run_id: Optional[str] = None) -> Path:
    """Return the path to the latest *_trend_objects.json in runs_dir."""
    pattern = f"{run_id}_trend_objects.json" if run_id else "*_trend_objects.json"
    candidates = sorted(runs_dir.glob(pattern))
    if not candidates:
        sys.exit(f"[ERROR] No trend_objects.json files found in {runs_dir}")
    return candidates[-1]


def tokenize_label(label: str) -> List[str]:
    """Split a trend label into lowercased word tokens."""
    return [w.lower() for w in re.findall(r"[A-Za-z\u4e00-\u9fff]+", label)]


def keyword_set(label: str) -> Set[str]:
    """Return a set of keyword tokens from a label, excluding very short words."""
    return {w for w in tokenize_label(label) if len(w) > 1}


def keyword_overlap_ratio(set_a: Set[str], set_b: Set[str]) -> float:
    """Return the fraction of shared keywords relative to the smaller set."""
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    smaller = min(len(set_a), len(set_b))
    return len(intersection) / smaller


GENERIC_WORDS = {"mixed", "miscellaneous", "other"}


# ---------------------------------------------------------------------------
# Check 1: Duplication Rate
# ---------------------------------------------------------------------------

def check_duplication(trends: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Detect near-duplicate labels (>60% keyword overlap) and shared post_ids."""
    results: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []

    # --- Label similarity ---
    label_sets = {t["trend_id"]: keyword_set(t["label"]) for t in trends}
    ids = list(label_sets.keys())
    similar_pairs: List[Tuple[str, str, float]] = []

    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            ratio = keyword_overlap_ratio(label_sets[ids[i]], label_sets[ids[j]])
            if ratio > 0.60:
                similar_pairs.append((ids[i], ids[j], round(ratio, 3)))

    # --- Shared post_ids across trends ---
    post_id_map: Dict[str, List[str]] = {}  # post_id -> list of trend_ids
    for t in trends:
        evidence = t.get("evidence", {})
        for pid in evidence.get("post_ids", []):
            post_id_map.setdefault(pid, []).append(t["trend_id"])

    shared_posts: List[Dict[str, Any]] = []
    for pid, tids in post_id_map.items():
        if len(tids) > 1:
            shared_posts.append({"post_id": pid, "in_trends": tids})

    # --- Per-trend pass/fail ---
    flagged_trend_ids: Set[str] = set()
    for a, b, ratio in similar_pairs:
        flagged_trend_ids.add(a)
        flagged_trend_ids.add(b)
    for sp in shared_posts:
        for tid in sp["in_trends"]:
            flagged_trend_ids.add(tid)

    for t in trends:
        tid = t["trend_id"]
        passed = tid not in flagged_trend_ids
        entry = {"trend_id": tid, "label": t["label"], "passed": passed, "issues": []}
        # Collect specific issues
        for a, b, ratio in similar_pairs:
            if tid in (a, b):
                other = b if tid == a else a
                issue = f"Label too similar to {other} (overlap {ratio*100:.0f}%)"
                entry["issues"].append(issue)
        for sp in shared_posts:
            if tid in sp["in_trends"]:
                issue = f"post_id {sp['post_id']} shared with {[x for x in sp['in_trends'] if x != tid]}"
                entry["issues"].append(issue)
        results.append(entry)
        if not passed:
            failures.append(entry)

    passed_count = sum(1 for r in results if r["passed"])
    return {
        "check": "duplication_rate",
        "passed": len(similar_pairs) == 0 and len(shared_posts) == 0,
        "pass_rate": f"{passed_count}/{len(results)}",
        "similar_label_pairs": [{"trend_a": a, "trend_b": b, "overlap": r} for a, b, r in similar_pairs],
        "shared_post_ids": shared_posts,
        "per_trend": results,
        "failures": failures,
    }


# ---------------------------------------------------------------------------
# Check 2: Evidence Sufficiency
# ---------------------------------------------------------------------------

def check_evidence_sufficiency(trends: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Each trend needs >=2 snippets, >=2 posts in evidence, and post_count >= 3."""
    results: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []

    for t in trends:
        tid = t["trend_id"]
        evidence = t.get("evidence", {})
        metrics = t.get("metrics", {})

        snippet_count = len(evidence.get("snippets", []))
        evidence_post_count = len(evidence.get("posts", []))
        post_count = metrics.get("post_count", 0)

        issues: List[str] = []
        if snippet_count < 2:
            issues.append(f"Only {snippet_count} snippet(s), need >=2")
        if evidence_post_count < 2:
            issues.append(f"Only {evidence_post_count} evidence post(s), need >=2")
        if post_count < 3:
            issues.append(f"post_count={post_count}, need >=3")

        passed = len(issues) == 0
        entry = {
            "trend_id": tid,
            "label": t["label"],
            "passed": passed,
            "snippet_count": snippet_count,
            "evidence_post_count": evidence_post_count,
            "post_count": post_count,
            "issues": issues,
        }
        results.append(entry)
        if not passed:
            failures.append(entry)

    passed_count = sum(1 for r in results if r["passed"])
    return {
        "check": "evidence_sufficiency",
        "passed": all(r["passed"] for r in results),
        "pass_rate": f"{passed_count}/{len(results)}",
        "per_trend": results,
        "failures": failures,
    }


# ---------------------------------------------------------------------------
# Check 3: Label Clarity Proxy
# ---------------------------------------------------------------------------

def check_label_clarity(trends: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Labels must be <=8 words, not generic, and distinct from each other."""
    results: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []

    # Pre-compute all label token sets for distinctness check
    label_tokens = {t["trend_id"]: set(tokenize_label(t["label"])) for t in trends}

    for t in trends:
        tid = t["trend_id"]
        label = t["label"]
        words = tokenize_label(label)
        word_count = len(words)
        lower_label = label.lower()

        issues: List[str] = []

        # Word count check
        if word_count > 8:
            issues.append(f"Label has {word_count} words, max is 8")

        # Generic term check
        for generic in GENERIC_WORDS:
            if generic in lower_label:
                issues.append(f"Label contains generic term '{generic}'")

        # Distinctness: flag if this label shares >60% keywords with another
        my_kws = keyword_set(label)
        for other in trends:
            if other["trend_id"] == tid:
                continue
            other_kws = keyword_set(other["label"])
            ratio = keyword_overlap_ratio(my_kws, other_kws)
            if ratio > 0.60:
                issues.append(
                    f"Label not distinct from {other['trend_id']} "
                    f"('{other['label']}', overlap {ratio*100:.0f}%)"
                )

        passed = len(issues) == 0
        entry = {
            "trend_id": tid,
            "label": label,
            "word_count": word_count,
            "passed": passed,
            "issues": issues,
        }
        results.append(entry)
        if not passed:
            failures.append(entry)

    passed_count = sum(1 for r in results if r["passed"])
    return {
        "check": "label_clarity",
        "passed": all(r["passed"] for r in results),
        "pass_rate": f"{passed_count}/{len(results)}",
        "per_trend": results,
        "failures": failures,
    }


# ---------------------------------------------------------------------------
# Report Generation
# ---------------------------------------------------------------------------

def collect_top_failures(
    checks: List[Dict[str, Any]], max_failures: int = 5
) -> List[Dict[str, Any]]:
    """Gather up to max_failures concrete failure examples across all checks."""
    all_failures: List[Dict[str, Any]] = []
    for check in checks:
        check_name = check["check"]
        for f in check.get("failures", []):
            all_failures.append({
                "check": check_name,
                "trend_id": f["trend_id"],
                "label": f["label"],
                "issues": f["issues"],
            })
    return all_failures[:max_failures]


def generate_report(
    run_data: Dict[str, Any],
    checks: List[Dict[str, Any]],
    top_failures: List[Dict[str, Any]],
    run_file: Path,
) -> str:
    """Generate EVAL_REPORT.md content."""
    run_id = run_data.get("run_id", "unknown")
    brand = run_data.get("brand", "unknown")
    generated_at = run_data.get("generated_at_utc", "unknown")
    trend_count = len(run_data.get("trend_objects", []))
    records_loaded = run_data.get("retrieval", {}).get("records_loaded", "?")
    records_retrieved = run_data.get("retrieval", {}).get("records_retrieved", "?")

    lines: List[str] = []
    lines.append("# Module 1 Evaluation Report")
    lines.append("")
    lines.append("## Run Metadata")
    lines.append("")
    lines.append(f"- **Run ID**: {run_id}")
    lines.append(f"- **Brand**: {brand}")
    lines.append(f"- **Generated at**: {generated_at}")
    lines.append(f"- **Eval run date**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append(f"- **Source file**: `{run_file.name}`")
    lines.append(f"- **Trend objects**: {trend_count}")
    lines.append(f"- **Dataset size**: {records_loaded} loaded, {records_retrieved} retrieved")
    lines.append("")

    # --- Results per check ---
    lines.append("## Quality Check Results")
    lines.append("")

    overall_pass_count = 0
    overall_total = 0

    for check in checks:
        check_name = check["check"].replace("_", " ").title()
        overall_passed = "PASS" if check["passed"] else "FAIL"
        lines.append(f"### {check_name}")
        lines.append("")
        lines.append(f"**Overall**: {overall_passed} ({check['pass_rate']} trends passed)")
        lines.append("")

        # Per-trend table
        lines.append("| Trend ID | Label | Result | Issues |")
        lines.append("|----------|-------|--------|--------|")
        for entry in check["per_trend"]:
            result_str = "PASS" if entry["passed"] else "FAIL"
            issues_str = "; ".join(entry["issues"]) if entry["issues"] else "--"
            label_escaped = entry["label"].replace("|", "\\|")
            issues_escaped = issues_str.replace("|", "\\|")
            lines.append(f"| {entry['trend_id']} | {label_escaped} | {result_str} | {issues_escaped} |")
        lines.append("")

        # Tally
        per_trend = check["per_trend"]
        p = sum(1 for r in per_trend if r["passed"])
        overall_pass_count += p
        overall_total += len(per_trend)

    overall_rate = (overall_pass_count / overall_total * 100) if overall_total else 0
    lines.append(f"**Aggregate pass rate**: {overall_pass_count}/{overall_total} ({overall_rate:.0f}%)")
    lines.append("")

    # --- Top 5 Failures ---
    lines.append("## Top Failures")
    lines.append("")
    if not top_failures:
        lines.append("No failures detected -- all checks passed.")
    else:
        for i, f in enumerate(top_failures, 1):
            lines.append(f"### Failure {i}")
            lines.append("")
            lines.append(f"- **Trend ID**: {f['trend_id']}")
            lines.append(f"- **Label**: {f['label']}")
            lines.append(f"- **Check**: {f['check'].replace('_', ' ').title()}")
            lines.append(f"- **What failed**: {'; '.join(f['issues'])}")
            lines.append("")

    # --- Recommendation ---
    lines.append("## Recommended Fix for Next Week")
    lines.append("")

    # Pick a recommendation based on which checks failed
    failed_checks = [c["check"] for c in checks if not c["passed"]]
    if "evidence_sufficiency" in failed_checks:
        lines.append(
            "**Raise the minimum cluster size threshold in the trend builder.** "
            "Trends with post_count < 3 or fewer than 2 evidence posts lack the "
            "supporting signal needed for downstream use. Adjust the clustering "
            "parameters to merge small clusters into their nearest neighbor or "
            "drop them entirely, rather than emitting under-evidenced trend objects."
        )
    elif "duplication_rate" in failed_checks:
        lines.append(
            "**Add a post-clustering deduplication pass.** After initial clustering, "
            "compare all trend label keyword sets and merge any pair whose overlap "
            "exceeds 60%. Also enforce that each post_id belongs to exactly one "
            "trend object to prevent evidence leakage across trends."
        )
    elif "label_clarity" in failed_checks:
        lines.append(
            "**Tighten the LLM label prompt constraints.** Add explicit instructions "
            "to the labeling prompt that labels must be <= 8 words, must not use "
            "generic filler words (Mixed, Miscellaneous, Other), and must be "
            "semantically distinct from all other labels in the same run."
        )
    else:
        lines.append(
            "All checks passed. Consider adding more checks: sentiment consistency "
            "within clusters, engagement distribution normality, or temporal spread "
            "of evidence posts across the time window."
        )

    lines.append("")
    lines.append("---")
    lines.append(f"*Generated by eval_harness.py on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate Module 1 trend objects for quality."
    )
    parser.add_argument(
        "--run",
        type=str,
        default=None,
        help="Specific run_id to evaluate (e.g. run_0013). Defaults to latest.",
    )
    parser.add_argument(
        "--runs-dir",
        type=str,
        default=str(RUNS_DIR),
        help="Directory containing run output files.",
    )
    args = parser.parse_args()

    runs_dir = Path(args.runs_dir)
    run_file = find_latest_run(runs_dir, run_id=args.run)
    print(f"[eval] Loading: {run_file.name}")

    with run_file.open("r", encoding="utf-8") as f:
        run_data = json.load(f)

    trends = run_data.get("trend_objects", [])
    if not trends:
        sys.exit("[ERROR] No trend_objects found in the run file.")

    print(f"[eval] Found {len(trends)} trend object(s) in {run_data.get('run_id', '?')}")
    print()

    # --- Run checks ---
    check_duplication_result = check_duplication(trends)
    check_evidence_result = check_evidence_sufficiency(trends)
    check_label_result = check_label_clarity(trends)

    checks = [check_duplication_result, check_evidence_result, check_label_result]

    # --- Print summary ---
    all_passed = True
    for check in checks:
        name = check["check"].replace("_", " ").title()
        status = "PASS" if check["passed"] else "FAIL"
        if not check["passed"]:
            all_passed = False
        print(f"  [{status}] {name} -- {check['pass_rate']} trends passed")
        for entry in check["per_trend"]:
            if not entry["passed"]:
                for issue in entry["issues"]:
                    print(f"         ^ {entry['trend_id']}: {issue}")

    print()
    overall_status = "ALL CHECKS PASSED" if all_passed else "SOME CHECKS FAILED"
    print(f"[eval] Result: {overall_status}")

    # --- Gather top failures ---
    top_failures = collect_top_failures(checks, max_failures=5)

    # --- Write eval_results.json ---
    eval_results = {
        "run_id": run_data.get("run_id"),
        "eval_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_file": run_file.name,
        "trend_count": len(trends),
        "all_passed": all_passed,
        "checks": checks,
        "top_failures": top_failures,
    }

    results_path = OUTPUT_DIR / "eval_results.json"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    with results_path.open("w", encoding="utf-8") as f:
        json.dump(eval_results, f, indent=2, ensure_ascii=False)
    print(f"[eval] JSON results written to {results_path}")

    # --- Generate EVAL_REPORT.md ---
    report_md = generate_report(run_data, checks, top_failures, run_file)
    report_path = OUTPUT_DIR / "EVAL_REPORT.md"
    with report_path.open("w", encoding="utf-8") as f:
        f.write(report_md)
    print(f"[eval] Markdown report written to {report_path}")


if __name__ == "__main__":
    main()
