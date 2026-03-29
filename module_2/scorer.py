"""
scorer.py — Deterministic pre-filter for Module 2 Trend Relevance & Materiality Filter Agent.

Rejects trends immediately without calling the LLM if they fail hard structural rules.
This keeps LLM costs low and response time fast by removing obvious non-qualifiers early.
"""

from datetime import datetime, timezone
from typing import Optional

# Reference date: the run date
TODAY = datetime.fromisoformat("2026-03-25").replace(tzinfo=timezone.utc)
STALENESS_CUTOFF_DAYS = 21  # reject if last post is older than this
STALENESS_CUTOFF_DATE = datetime(2026, 3, 4, tzinfo=timezone.utc)  # 2026-03-25 minus 21 days

MIN_POST_COUNT = 5
MIN_TOTAL_ENGAGEMENT = 3000
MIN_SNIPPETS = 2


def _get_last_post_date(trend: dict) -> Optional[datetime]:
    """Extract the most recent post date from evidence.posts."""
    posts = trend.get("evidence", {}).get("posts", [])
    if not posts:
        return None
    dates = []
    for post in posts:
        raw = post.get("date", "")
        if not raw:
            continue
        try:
            # Handle both date-only and datetime strings
            if "T" in raw:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            else:
                dt = datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
            dates.append(dt)
        except ValueError:
            continue
    return max(dates) if dates else None


def _contains_taboo(text: str, taboos: list) -> Optional[str]:
    """Return the first matching taboo keyword found in text, or None."""
    text_lower = text.lower()
    for taboo in taboos:
        if taboo.lower() in text_lower:
            return taboo
    return None


def pre_filter(trend: dict, brand_profile: dict) -> "tuple[bool, Optional[str]]":
    """
    Apply deterministic pre-filter rules to a single trend object.

    Returns:
        (passed: bool, rejection_reason: str or None)
        If passed=True, rejection_reason is None.
        If passed=False, rejection_reason explains why.
    """
    trend_id = trend.get("trend_id", "unknown")
    label = trend.get("label", "")
    summary = trend.get("summary", "")
    category = trend.get("category", "")
    metrics = trend.get("metrics", {})
    evidence = trend.get("evidence", {})
    snippets = evidence.get("snippets", [])

    active_categories = brand_profile.get("active_categories", [])
    brand_taboos = brand_profile.get("brand_taboos", [])

    # Rule 1: Category must be active
    if category not in active_categories:
        return False, f"Category '{category}' not in brand active_categories {active_categories}"

    # Rule 2: Minimum post count
    # luxury_fashion with 2–4 posts: pass with low_signal_warning (niche signals still valuable)
    # All other categories: hard reject below MIN_POST_COUNT
    post_count = metrics.get("post_count", 0)
    if post_count < MIN_POST_COUNT:
        if category == "luxury_fashion" and post_count >= 2:
            trend["low_signal_warning"] = (
                f"post_count={post_count} is below {MIN_POST_COUNT} — "
                "passed to LLM with low_signal warning"
            )
            # Do not return False — let it through to LLM evaluation
        else:
            return False, f"post_count={post_count} is below minimum threshold of {MIN_POST_COUNT}"

    # Rule 3: Minimum total engagement
    total_engagement = metrics.get("total_engagement", 0)
    if total_engagement < MIN_TOTAL_ENGAGEMENT:
        return False, f"total_engagement={total_engagement} is below minimum threshold of {MIN_TOTAL_ENGAGEMENT}"

    # Rule 4: Freshness — last post must be within 21 days of today (2026-03-25)
    last_post_date = _get_last_post_date(trend)
    if last_post_date is None:
        return False, "No valid post dates found in evidence.posts — cannot assess freshness"
    if last_post_date < STALENESS_CUTOFF_DATE:
        return False, (
            f"Last post date {last_post_date.date()} is before staleness cutoff "
            f"{STALENESS_CUTOFF_DATE.date()} (>{STALENESS_CUTOFF_DAYS} days before 2026-03-25)"
        )

    # Rule 5: Minimum snippet count
    if len(snippets) < MIN_SNIPPETS:
        return False, f"Only {len(snippets)} snippet(s) found — minimum required is {MIN_SNIPPETS}"

    # Rule 6: Brand taboo keywords in label or summary
    combined_text = f"{label} {summary}"
    matched_taboo = _contains_taboo(combined_text, brand_taboos)
    if matched_taboo:
        return False, f"Brand taboo keyword '{matched_taboo}' detected in label/summary"

    return True, None


def run_prefilter_batch(trends: list, brand_profile: dict) -> "tuple[list, list]":
    """
    Run pre-filter across all trends.

    Returns:
        (passed_trends: list, rejected_log: list)
        passed_trends: trends that survived the pre-filter
        rejected_log: list of dicts with trend_id, label, reason
    """
    passed = []
    rejected = []

    for trend in trends:
        ok, reason = pre_filter(trend, brand_profile)
        if ok:
            passed.append(trend)
            warning = trend.get("low_signal_warning")
            if warning:
                print(f"  ⚠ [{trend.get('trend_id', 'unknown')}] {trend.get('label', '')} — {warning}")
        else:
            rejected.append({
                "trend_id": trend.get("trend_id", "unknown"),
                "label": trend.get("label", ""),
                "reason": reason,
            })

    return passed, rejected
