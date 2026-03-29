"""
prompts.py — LLM prompt templates for Module 2 Trend Relevance & Materiality Filter Agent.

Brand name and profile details are injected at runtime so the module works for any luxury brand.
"""

import json


def build_system_prompt(brand_profile: dict) -> str:
    brand_name = brand_profile.get("brand_name", "the brand")
    aesthetic = brand_profile.get("aesthetic", "luxury and refined craftsmanship")
    clientele = brand_profile.get("clientele", "affluent clients who value heritage")
    tone = brand_profile.get("clienteling_tone", "expert, aspirational, warm but refined")
    return (
        f"You are a senior luxury retail trend analyst specializing in Chinese consumer behavior "
        f"on Xiaohongshu, with deep expertise in the {brand_name} brand. "
        f"You evaluate trend signals and decide which trends are truly material, brand-appropriate "
        f"for {brand_name}, and actionable for {brand_name} Client Advisors. "
        f"You are evidence-grounded and precise. "
        f"You never shortlist a trend just because it is popular — it must reflect {brand_name}'s "
        f"aesthetic ({aesthetic}), match the {brand_name} clientele ({clientele}), "
        f"and be genuinely usable in a {brand_name} clienteling conversation (tone: {tone}). "
        f"You always cite specific snippets or metrics in your reasoning. "
        f"You never write generic statements like 'this trend aligns with {brand_name} values' "
        f"without explaining exactly why with specific evidence from the trend object."
    )


def build_batch_evaluation_prompt(brand_profile: dict, trend_objects: list, today: str = "2026-03-25") -> str:
    """
    Build a batch evaluation prompt for up to 5 trend objects at once.
    Returns a prompt asking the LLM to return a JSON array of evaluations.
    """
    brand_name = brand_profile.get("brand_name", "the brand")
    aesthetic = brand_profile.get("aesthetic", "luxury and refined craftsmanship")
    clientele = brand_profile.get("clientele", "affluent clients who value heritage")
    category_cadence = brand_profile.get("category_cadence", {})
    rtw_pace = category_cadence.get("ready-to-wear", "fast")
    lg_pace = category_cadence.get("leather goods", "medium")
    preferred_sources = ", ".join(brand_profile.get("preferred_sources", ["luxury KOL", "fashion editorial"]))

    brand_profile_str = json.dumps(brand_profile, ensure_ascii=False, indent=2)
    trends_str = json.dumps(trend_objects, ensure_ascii=False, indent=2)

    return f"""You are evaluating a batch of trend objects for {brand_name}.

Brand Profile:
{brand_profile_str}

Today's date: {today}

Trend Objects (batch of {len(trend_objects)}):
{trends_str}

For EACH trend object in the batch, score it on these 5 dimensions (0–10 each). For each score you must cite specific evidence from that trend object — a snippet, a metric, a keyword, a date. Do not write generic reasoning.

Dimensions:

1. FRESHNESS (0–10): Is this trend still gaining traction as of today? Look at the dates in evidence.posts — are the most recent posts within the last 2 weeks? Is there a pattern of growing or fading momentum across the post dates?

2. BRAND FIT (0–10): Does this trend match {brand_name}'s aesthetic ({aesthetic})? Does it match the {brand_name} clientele ({clientele})? Do the creator types in evidence.posts align with {brand_name}'s preferred sources ({preferred_sources})? Would a {brand_name} CA feel genuinely comfortable raising this trend in a client conversation?

3. CATEGORY FIT (0–10): Is this trend appropriate for this specific product category? Ready-to-wear moves {rtw_pace} — recency and momentum matter most. Leather goods moves at {lg_pace} pace — sustained signal across multiple weeks matters more than single viral moments.

4. MATERIALITY (0–10): Is total_engagement strong enough to be meaningful for a luxury brand audience on XHS? Is engagement spread across multiple posts rather than one viral outlier? Does post_count show real sustained interest over time?

5. ACTIONABILITY (0–10): Can a {brand_name} CA mention this trend naturally in a refined client conversation? Is it specific enough to be useful — not just "feminine dressing is trending" but something concrete a CA can reference with a specific {brand_name} product or look? Would an affluent {brand_name} client respond positively and feel the CA is knowledgeable?

Compute composite_score as:
(freshness × 0.20) + (brand_fit × 0.30) + (category_fit × 0.20) + (materiality × 0.15) + (actionability × 0.15)

A trend is shortlisted ONLY if:
- composite_score >= 6.5
- No individual dimension score is below 4
- You judge it genuinely usable for {brand_name} CAs right now

Return ONLY a valid JSON array with no markdown and no text outside the JSON. One object per trend, in the same order as the input batch:
[
  {{
    "trend_id": "string",
    "shortlist": true or false,
    "scores": {{
      "freshness": number,
      "brand_fit": number,
      "category_fit": number,
      "materiality": number,
      "actionability": number
    }},
    "composite_score": number,
    "reasoning": "3-5 sentences, specific and evidence-grounded. Must cite at least one snippet or metric by name. Must explain why this is or is not right for {brand_name} specifically.",
    "confidence": "high" or "medium" or "low",
    "evidence_references": ["direct quote or metric from the trend object that supports the decision"],
    "disqualifying_reason": null or "exact dimension that failed and why"
  }}
]"""
