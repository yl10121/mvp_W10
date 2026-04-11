"""
scorer.py — Deterministic pre-filter for Module 2 Trend Relevance & Materiality Filter Agent.

Rejects trends before any LLM call if they fail hard structural rules.
Also handles cross-run deduplication and engagement recency calculation.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

# Reference date for the data collection window
TODAY = datetime.fromisoformat("2026-03-25").replace(tzinfo=timezone.utc)
STALENESS_CUTOFF_DAYS = 21
STALENESS_CUTOFF_DATE = datetime(2026, 3, 4, tzinfo=timezone.utc)

MIN_POST_COUNT = 5
MIN_SNIPPETS = 2
MIN_BRAND_SIGNAL_SNIPPETS = 2  # min snippets containing Celine-specific language
SIMILARITY_THRESHOLD = 0.70   # Jaccard threshold for cross-run deduplication
RECENCY_DAYS = 7              # window for engagement_recency_pct calculation

CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1, "": 0}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _flatten_taboos(taboos) -> list:
    """Handle brand_taboos whether it's a flat list or a dict of lists."""
    if isinstance(taboos, list):
        return taboos
    if isinstance(taboos, dict):
        flat = []
        for group in taboos.values():
            if isinstance(group, list):
                flat.extend(group)
        return flat
    return []


def _get_hero_product_names(brand_profile: dict) -> list:
    """Extract all hero product name strings from brand_profile.hero_products."""
    hero = brand_profile.get("hero_products", {})
    if isinstance(hero, list):
        return [str(p) for p in hero]
    names = []
    for cat_products in hero.values():
        if isinstance(cat_products, list):
            names.extend([str(p) for p in cat_products])
    return names


def _get_pillar_keywords(brand_profile: dict) -> list:
    """
    Extract searchable keywords from brand_profile.aesthetic_pillars.
    Uses individual words from pillar names (length > 3) as signal terms.
    e.g. 'The Triomphe Identity' → ['triomphe', 'identity']
    """
    keywords = []
    for pillar in brand_profile.get("aesthetic_pillars", []):
        name = pillar.get("name", "")
        for word in name.lower().split():
            if len(word) > 3 and word not in {"with", "from", "that", "this", "without"}:
                keywords.append(word)
    return list(set(keywords))


def _jaccard_similarity(text1: str, text2: str) -> float:
    """Jaccard word-token similarity between two strings."""
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    if not words1 and not words2:
        return 1.0
    if not words1 or not words2:
        return 0.0
    return len(words1 & words2) / len(words1 | words2)


def _merge_trends(primary: dict, secondary: dict) -> dict:
    """
    Merge two similar trends. Primary wins on ID/label/summary.
    Evidence snippets and posts are combined. Post counts and engagement are summed.
    data_type is set to 'merged'. run_count accumulates.
    """
    merged = dict(primary)

    # Combine snippets (deduplicated, order preserved)
    snippets_a = primary.get("evidence", {}).get("snippets", [])
    snippets_b = secondary.get("evidence", {}).get("snippets", [])
    merged_snippets = list(dict.fromkeys(snippets_a + snippets_b))

    # Combine posts (deduplicated by post_id)
    posts_a = primary.get("evidence", {}).get("posts", [])
    posts_b = secondary.get("evidence", {}).get("posts", [])
    seen_ids = {p.get("post_id") for p in posts_a}
    merged_posts = list(posts_a)
    for p in posts_b:
        if p.get("post_id") not in seen_ids:
            merged_posts.append(p)
            seen_ids.add(p.get("post_id"))

    merged["evidence"] = dict(primary.get("evidence", {}))
    merged["evidence"]["snippets"] = merged_snippets
    merged["evidence"]["posts"] = merged_posts

    # Sum metrics
    metrics_a = primary.get("metrics", {})
    metrics_b = secondary.get("metrics", {})
    merged["metrics"] = dict(metrics_a)
    merged["metrics"]["post_count"] = (
        metrics_a.get("post_count", 0) + metrics_b.get("post_count", 0)
    )
    merged["metrics"]["total_engagement"] = (
        metrics_a.get("total_engagement", 0) + metrics_b.get("total_engagement", 0)
    )
    pc = merged["metrics"]["post_count"]
    if pc > 0:
        merged["metrics"]["avg_engagement"] = round(
            merged["metrics"]["total_engagement"] / pc, 1
        )

    merged["data_type"] = "merged"
    merged["run_count"] = primary.get("run_count", 1) + secondary.get("run_count", 1)
    return merged


# ── New Rule A: Cross-run deduplication ───────────────────────────────────────

def deduplicate_batch(trends: list) -> "tuple[list, int]":
    """
    Cross-run deduplication. Compares all trend objects by Jaccard similarity
    of combined label+summary text. If similarity >= SIMILARITY_THRESHOLD,
    merges them into one object (higher-confidence trend wins as primary).

    Returns (deduplicated_list, merge_count).
    Called once at the top of run_prefilter_batch before per-trend rules.
    """
    if not trends:
        return trends, 0

    # Sort descending by confidence so primary is always the more confident trend
    candidates = sorted(
        trends,
        key=lambda t: CONFIDENCE_RANK.get(t.get("confidence", ""), 0),
        reverse=True,
    )

    merged_into: set = set()
    result = []
    merge_count = 0

    for i, trend_a in enumerate(candidates):
        if i in merged_into:
            continue
        current = dict(trend_a)
        current.setdefault("run_count", 1)
        text_a = f"{trend_a.get('label', '')} {trend_a.get('summary', '')}"

        for j, trend_b in enumerate(candidates):
            if j <= i or j in merged_into:
                continue
            text_b = f"{trend_b.get('label', '')} {trend_b.get('summary', '')}"
            if _jaccard_similarity(text_a, text_b) >= SIMILARITY_THRESHOLD:
                current = _merge_trends(current, trend_b)
                merged_into.add(j)
                merge_count += 1

        result.append(current)

    return result, merge_count


# ── New Rule B: Engagement recency calculation ─────────────────────────────────

def compute_engagement_recency(
    trend: dict,
    today: datetime = TODAY,
    days: int = RECENCY_DAYS,
) -> float:
    """
    Calculate what % of total engagement (likes + comments + saves) came from
    posts dated within the last N days. Stores result on trend as
    engagement_recency_pct for use in LLM trend_velocity scoring.
    """
    posts = trend.get("evidence", {}).get("posts", [])
    cutoff = today - timedelta(days=days)
    recent_eng = 0
    total_eng = 0

    for post in posts:
        likes = post.get("likes", 0) or 0
        comments = post.get("comments", 0) or 0
        saves = post.get("saves", 0) or 0
        eng = likes + comments + saves
        total_eng += eng

        raw_date = post.get("date", "")
        if not raw_date:
            continue
        try:
            if "T" in raw_date:
                dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            else:
                dt = datetime.fromisoformat(raw_date).replace(tzinfo=timezone.utc)
            if dt >= cutoff:
                recent_eng += eng
        except ValueError:
            pass

    pct = round(recent_eng / total_eng * 100, 1) if total_eng > 0 else 0.0
    trend["engagement_recency_pct"] = pct
    return pct


# ── Existing helpers ───────────────────────────────────────────────────────────

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


# ── Per-trend pre-filter ───────────────────────────────────────────────────────

def pre_filter(trend: dict, brand_profile: dict) -> "tuple[bool, Optional[str]]":
    """
    Apply deterministic pre-filter rules to a single trend object.

    Returns:
        (passed: bool, rejection_reason: str or None)
    """
    label = trend.get("label", "")
    summary = trend.get("summary", "")
    category = trend.get("category", "")
    data_type = trend.get("data_type", "real")
    metrics = trend.get("metrics", {})
    evidence = trend.get("evidence", {})
    snippets = evidence.get("snippets", [])

    active_categories = brand_profile.get("active_categories", [])
    brand_taboos = _flatten_taboos(brand_profile.get("brand_taboos", []))

    # Rule 1: Category must be active
    if category not in active_categories:
        return False, f"Category '{category}' not in brand active_categories {active_categories}"

    # Rule 2: Minimum post count
    # luxury_fashion with 2–4 posts: pass with low_signal_warning
    # All other categories: hard reject below MIN_POST_COUNT
    post_count = metrics.get("post_count", 0)
    if post_count < MIN_POST_COUNT:
        if category == "luxury_fashion" and post_count >= 2:
            trend["low_signal_warning"] = (
                f"post_count={post_count} is below {MIN_POST_COUNT} — "
                "passed to LLM with low_signal warning"
            )
        else:
            return False, f"post_count={post_count} is below minimum threshold of {MIN_POST_COUNT}"

    # Rule 3: REMOVED — engagement volume is not a hard disqualifier for luxury brands.
    # Low engagement flows into trend_velocity scoring in LLM evaluation instead.

    # Rule 4: Freshness — hard reject only when dates are confirmed older than 21 days.
    # If no valid dates found at all, pass with no_date_signal warning for LLM assessment.
    last_post_date = _get_last_post_date(trend)
    if last_post_date is None:
        trend["no_date_signal"] = (
            "No valid post dates found in evidence.posts — "
            "LLM will assess freshness from content quality"
        )
    elif last_post_date < STALENESS_CUTOFF_DATE:
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

    # Rule 7: Brand signal strength check — real XHS trends only (synthetic pass automatically)
    # Requires at least MIN_BRAND_SIGNAL_SNIPPETS snippets containing Celine-specific language:
    # brand name, hero product name, or aesthetic pillar keyword.
    if data_type == "real":
        brand_name = brand_profile.get("brand_name", "")
        brand_name_cn = brand_profile.get("brand_name_cn", "")
        hero_names = _get_hero_product_names(brand_profile)
        pillar_keywords = _get_pillar_keywords(brand_profile)
        signal_terms = [
            t.lower() for t in [brand_name, brand_name_cn] + hero_names + pillar_keywords if t
        ]

        signal_count = sum(
            1 for snippet in snippets
            if any(term in snippet.lower() for term in signal_terms)
        )
        if signal_count < MIN_BRAND_SIGNAL_SNIPPETS:
            return False, (
                f"Insufficient brand signal in snippets — only {signal_count} of "
                f"{len(snippets)} snippet(s) mention Celine brand name, "
                f"a hero product, or an aesthetic pillar keyword "
                f"(minimum required: {MIN_BRAND_SIGNAL_SNIPPETS})"
            )

    return True, None


# ── Batch entry point ──────────────────────────────────────────────────────────

def run_prefilter_batch(trends: list, brand_profile: dict) -> "tuple[list, list]":
    """
    Run pre-filter across all trends.

    Processing order:
      Step A — Cross-run deduplication (batch-level, merges near-duplicates)
      Step B — Engagement recency calculation (per trend, stores engagement_recency_pct)
      Step C — Per-trend pre-filter rules 1–2, 4–7 (Rule 3 engagement threshold removed)

    Returns:
        (passed_trends: list, rejected_log: list)
    """
    # Step A: Cross-run deduplication
    trends, merge_count = deduplicate_batch(trends)
    if merge_count > 0:
        print(
            f"  [Dedup] Merged {merge_count} near-duplicate pair(s) "
            f"(>{SIMILARITY_THRESHOLD*100:.0f}% similarity). "
            f"Batch now: {len(trends)} trends."
        )
    else:
        print(
            f"  [Dedup] No duplicates above {SIMILARITY_THRESHOLD*100:.0f}% "
            f"similarity threshold."
        )

    # Step B: Compute engagement recency for all trends
    for trend in trends:
        compute_engagement_recency(trend)

    # Step C: Per-trend pre-filter
    passed = []
    rejected = []

    for trend in trends:
        ok, reason = pre_filter(trend, brand_profile)
        if ok:
            passed.append(trend)
            warning = trend.get("low_signal_warning")
            if warning:
                print(
                    f"  ⚠ [{trend.get('trend_id', 'unknown')}] "
                    f"{trend.get('label', '')} — {warning}"
                )
        else:
            rejected.append({
                "trend_id": trend.get("trend_id", "unknown"),
                "label": trend.get("label", ""),
                "reason": reason,
            })

    return passed, rejected
