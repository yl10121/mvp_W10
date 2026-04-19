"""
prompts.py — LLM prompt templates for Module 2 Trend Relevance & Materiality Filter Agent.

Scores 4 LLM dimensions per trend: brand_fit, ca_conversational_utility,
language_specificity, novelty. Two further dimensions (trend_velocity,
cross_run_persistence) are computed algorithmically by evaluator.py.

Persona matching is Module 3's responsibility — not done here.
No product recommendations, no archetype matching, no hero_product_link.
"""

import json


def build_system_prompt(brand_profile: dict) -> str:
    brand_name = brand_profile.get("brand_name", "the brand")
    aesthetic = brand_profile.get("aesthetic_dna", brand_profile.get("aesthetic", "luxury"))
    tone = brand_profile.get("clienteling_tone", "precise, expert, refined")
    voice = brand_profile.get("brand_voice", "confident and refined")
    director = brand_profile.get("current_creative_director", "")
    director_str = f" under {director}" if director else ""

    return (
        f"You are a senior luxury retail trend analyst specialising in Chinese consumer behaviour "
        f"on Xiaohongshu, with deep expertise in {brand_name}{director_str}. "
        f"You evaluate trend signals and decide which trends are truly material, brand-appropriate, "
        f"and actionable for {brand_name} Client Advisors in Shanghai. "
        f"You are evidence-grounded and precise. "
        f"\n\n"
        f"{brand_name} aesthetic: {aesthetic}. "
        f"Clienteling tone: {tone}. "
        f"Brand voice: {voice}. "
        f"\n\n"
        f"You never shortlist a trend just because it is popular — it must reflect {brand_name}'s "
        f"specific aesthetic and be genuinely usable in a {brand_name} CA conversation within the next 7 days. "
        f"You always cite specific snippets or metrics in your reasoning. "
        f"You never write generic statements like 'this aligns with {brand_name} values' "
        f"without explaining exactly why with specific evidence from the trend object."
    )


def build_batch_evaluation_prompt(
    brand_profile: dict,
    trend_objects: list,
    today: str = "2026-04-19",
) -> str:
    """
    Build a batch evaluation prompt for up to 5 trend objects.
    Brand context (aesthetic pillars, competitive positioning) is injected from brand_profile.
    Persona matching and product recommendations are NOT done here — those are Module 3's job.
    """
    brand_name = brand_profile.get("brand_name", "the brand")

    # ── Aesthetic pillars block ────────────────────────────────────────────────
    pillars = brand_profile.get("aesthetic_pillars", [])
    if pillars:
        pillar_lines = [
            f"  • {p['name']}: {p.get('description', '')}" for p in pillars
        ]
        pillar_block = (
            "AESTHETIC PILLARS (compare against these when scoring novelty):\n"
            + "\n".join(pillar_lines)
        )
        pillar_names = [p.get("name", "") for p in pillars]
    else:
        pillar_block = ""
        pillar_names = []

    pillar_names_str = ", ".join(pillar_names) if pillar_names else "the brand's aesthetic pillars"

    # ── Competitive context ────────────────────────────────────────────────────
    competitive = brand_profile.get("competitive_differentiation", {})
    if competitive:
        comp_lines = [f"  vs {k}: {v}" for k, v in competitive.items()]
        comp_note = "COMPETITIVE POSITIONING (use when scoring brand_fit and novelty):\n" + "\n".join(comp_lines)
    else:
        comp_note = ""

    trends_str = json.dumps(trend_objects, ensure_ascii=False, indent=2)

    return f"""You are evaluating a batch of trend objects for {brand_name}.

Today's date: {today}

{pillar_block}

{comp_note}

Trend Objects (batch of {len(trend_objects)}):
{trends_str}

──────────────────────────────────────────────────────────────
SCORING INSTRUCTIONS

For EACH trend object, score it on the 4 LLM dimensions below (0–10 each).
For EVERY score you must cite specific evidence — a snippet, a metric, a keyword. No generic reasoning.

DIMENSIONS:

1. BRAND_FIT (0–10)
Does this trend match {brand_name}'s aesthetic DNA? Would a {brand_name} CA feel genuinely comfortable raising it?
Use competitive context: if this trend is more relevant to a competitor's positioning, score low.
Cite a specific snippet or metric.

2. CA_CONVERSATIONAL_UTILITY (0–10)
Can a {brand_name} CA use this trend to open a client conversation within 7 days?

IMPORTANT: Check the trend for an "extracted_product" field — this means a product name was found organically in real XHS posts. If present, reference it directly in your reasoning.

Score 8–10: trend has an extracted_product that clearly anchors a CA conversation.
Score 6–7: trend is clearly linkable to a specific {brand_name} product category (e.g. engagement ring trend, self-purchase bracelet trend). No stretch required.
Score 4–5: trend is brand-relevant but the CA needs to work to connect it to a product — the link is real but not immediate.
Score 1–3: purely aesthetic or abstract — no plausible {brand_name} product category connection.

3. LANGUAGE_SPECIFICITY (0–10)
Are the XHS snippets using specific, vivid, quotable Chinese language a CA could echo to a client?
Score 8–10: snippets contain specific emotional or cultural references that feel authentic and reusable. Quote the most specific snippet.
Score 1–4: snippets are generic luxury descriptors with no distinctive voice.

4. NOVELTY (0–10)
Is this trend saying something genuinely new about how {brand_name}'s customers engage with the brand in China?
Compare against these pillars: {pillar_names_str}.
Score 7–10: offers a new specific cultural insight, new occasion trigger, or new product usage pattern not captured in existing pillars.
Score 1–4: purely confirms an existing pillar without adding a new angle.
Always name the pillar being confirmed or extended in matched_pillar.

NOTE: trend_velocity and cross_run_persistence are computed algorithmically from engagement_recency_pct and run_count. Do NOT score these yourself.

──────────────────────────────────────────────────────────────
COMPOSITE SCORE FORMULA (for reference only — system will recompute)
brand_fit×0.25 + ca_conversational_utility×0.25 + trend_velocity×0.20 + language_specificity×0.15 + novelty×0.10 + cross_run_persistence×0.05

SHORTLISTING CRITERIA
Shortlist ONLY if:
- All 4 LLM-scored dimensions >= 4 (ca_conversational_utility minimum = 4)
- composite_score >= 6.5 (system will recompute, but use this as your guide)
- Genuinely usable for {brand_name} CAs right now

──────────────────────────────────────────────────────────────
OUTPUT FORMAT

Return ONLY a valid JSON array — no markdown, no text outside the JSON. One object per trend, same order as input batch:
[
  {{
    "trend_id": "string",
    "shortlist": true or false,
    "scores": {{
      "brand_fit": number,
      "ca_conversational_utility": number,
      "language_specificity": number,
      "novelty": number
    }},
    "matched_pillar": "name of the aesthetic pillar this trend confirms or extends, or null",
    "composite_score": number,
    "reasoning": "3-5 sentences. Must: (1) explain specifically why this trend fits or fails {brand_name}'s aesthetic; (2) name the pillar confirmed or extended; (3) cite at least one snippet or metric as evidence; (4) note the extracted_product if present.",
    "confidence": "high" or "medium" or "low",
    "evidence_references": ["direct quote or metric from the trend object"],
    "disqualifying_reason": null or "exact dimension that failed and why"
  }}
]"""
