"""
prompts.py — LLM prompt templates for Module 2 Trend Relevance & Materiality Filter Agent.

8-dimension scoring system.
LLM scores 6 dimensions: brand_engagement_depth, client_touchpoint_specificity,
  vocabulary_transfer_potential, intelligence_value, client_segment_clarity,
  occasion_purchase_trigger.
Algorithmic: trend_velocity (engagement recency / save-ratio proxy),
             evidence_credibility (cross-run persistence × confidence weight).

Definition of relevance: a trend is relevant if it is fresh, brand-specific,
and gives a CA a concrete reason to contact a client this week.
"""

import json
from datetime import date


def build_system_prompt(brand_profile: dict) -> str:
    brand_name = brand_profile.get("brand_name", "the brand")
    aesthetic = brand_profile.get("aesthetic_dna", brand_profile.get("aesthetic", "luxury"))
    tone = brand_profile.get("clienteling_tone", "precise, expert, refined")
    voice = brand_profile.get("brand_voice", "confident and refined")
    director = brand_profile.get("current_creative_director", "")
    director_str = f" under {director}" if director else ""

    # Dynamic competitive context
    competitive = brand_profile.get("competitive_differentiation", {})
    if competitive:
        comp_lines = [f"  vs {k}: {v}" for k, v in competitive.items()]
        comp_str = "Competitive positioning:\n" + "\n".join(comp_lines)
    else:
        comp_str = ""

    # Dynamic aesthetic pillars
    pillars = brand_profile.get("aesthetic_pillars", [])
    if pillars:
        pillar_lines = [f"  • {p['name']}: {p.get('description', '')}" for p in pillars]
        pillar_str = "Aesthetic pillars:\n" + "\n".join(pillar_lines)
    else:
        pillar_str = ""

    return (
        f"You are a senior luxury retail intelligence analyst specialising in Chinese consumer "
        f"behaviour on Xiaohongshu, with deep expertise in {brand_name}{director_str}. "
        f"You decide which XHS trend signals give {brand_name} Client Advisors a concrete, "
        f"credible reason to contact a specific client this week. "
        f"You are evidence-grounded and precise — you never generalise.\n\n"
        f"{brand_name} aesthetic: {aesthetic}.\n"
        f"Clienteling tone: {tone}. Brand voice: {voice}.\n\n"
        f"{pillar_str}\n\n"
        f"{comp_str}\n\n"
        f"A trend is relevant ONLY if it is (1) fresh — real consumer language from the last "
        f"3 weeks, not just brand identity confirmation; (2) brand-specific — deep engagement "
        f"with {brand_name} products, language, or occasions, not generic luxury content; "
        f"(3) actionable — gives a CA a specific, non-pushy conversation starter this week. "
        f"You always cite specific snippets, metrics, or signal flags in your reasoning. "
        f"You never write 'this aligns with {brand_name} values' without citing evidence."
    )


def build_batch_evaluation_prompt(
    brand_profile: dict,
    trend_objects: list,
    today: str = None,
) -> str:
    """
    Build a batch evaluation prompt for up to 5 trend objects.
    LLM scores 6 of the 8 dimensions. trend_velocity and evidence_credibility
    are computed algorithmically after the LLM call.
    """
    if today is None:
        today = date.today().isoformat()

    brand_name = brand_profile.get("brand_name", "the brand")

    # Aesthetic pillars (for intelligence_value scoring)
    pillars = brand_profile.get("aesthetic_pillars", [])
    if pillars:
        pillar_lines = [
            f"  • {p['name']}: {p.get('description', '')}" for p in pillars
        ]
        pillar_block = (
            "AESTHETIC PILLARS (use when scoring intelligence_value — "
            "trends that merely confirm existing pillars score low):\n"
            + "\n".join(pillar_lines)
        )
        pillar_names_str = ", ".join(p.get("name", "") for p in pillars)
    else:
        pillar_block = ""
        pillar_names_str = "the brand's aesthetic pillars"

    # Competitive context (for brand_engagement_depth scoring)
    competitive = brand_profile.get("competitive_differentiation", {})
    if competitive:
        comp_lines = [f"  vs {k}: {v}" for k, v in competitive.items()]
        comp_note = (
            "COMPETITIVE CONTEXT (use when scoring brand_engagement_depth — "
            "content that is more relevant to a competitor scores lower):\n"
            + "\n".join(comp_lines)
        )
    else:
        comp_note = ""

    trends_str = json.dumps(trend_objects, ensure_ascii=False, indent=2)

    return f"""You are evaluating XHS trend signals for {brand_name} Client Advisors.

Today's date: {today}

{pillar_block}

{comp_note}

Trend Objects (batch of {len(trend_objects)}):
{trends_str}

──────────────────────────────────────────────────────────────
SCORING INSTRUCTIONS

Score each trend on the 6 LLM dimensions below (0–10 each).
For EVERY score: cite a specific snippet, metric, or signal flag. No generic reasoning.

SIGNAL FLAGS TO CHECK IN EACH TREND OBJECT:
- "extracted_product": a specific {brand_name} product name found organically in XHS posts
- "celebrity_signal": true if posts contain celebrity/endorsement language (明星/同款/代言人)
- "occasion_signal": true if posts contain purchase occasion triggers (求婚/纪念日/礼物/婚礼/生日)
- "competitor_signal": true if posts mention competitor brands; "competitor_mentions" lists which ones

If any signal flag is present, reference it explicitly in your reasoning and adjust scores accordingly.
celebrity_signal or occasion_signal should raise client_touchpoint_specificity by 2+ points.
competitor_signal with named brand should inform brand_engagement_depth scoring.

──────────────────────────────────────────────────────────────
DIMENSIONS:

1. BRAND_ENGAGEMENT_DEPTH (0–10)  weight: 0.20
Does this trend show consumers deeply engaged with {brand_name} specifically?
Deep engagement: specific product names, specific {brand_name} behaviors, specific brand language.
Generic luxury content that mentions the brand name scores 2–4.
Cite the most brand-specific snippet. Use competitive context: if the content is more relevant
to a competitor's positioning, score low (1–4).

2. CLIENT_TOUCHPOINT_SPECIFICITY (0–10)  weight: 0.20
Does this give a CA a specific, credible, non-pushy reason to contact a client this week?
Score 9–10: celebrity_signal present OR occasion_signal present OR extracted_product from real posts
Score 7–8: clearly links to a {brand_name} product category with specific vivid language
Score 5–6: brand-relevant but requires CA effort to connect — the link is real but not immediate
Score 3–4: too abstract for a specific CA conversation opener
Score 1–2: no clear client conversation application

3. VOCABULARY_TRANSFER_POTENTIAL (0–10)  weight: 0.15
Can a CA borrow this language naturally in a client conversation?
Reward: personal testimony (我/你/她/他), specific prices or numbers, comparison language
  (比/还是/vs), emotional occasion words (求婚/纪念/第一次/礼物), sensory descriptors.
Penalise: generic luxury adjectives (高端/奢华/精致 used vaguely), abstract aesthetic terms.
Quote the single most transferable phrase from the snippets.

4. INTELLIGENCE_VALUE (0–10)  weight: 0.10
Does this tell a CA something genuinely new they couldn't figure out themselves?
Reward: new consumer behaviors, specific competitive comparisons, emerging occasion triggers,
  unexpected product usage patterns.
Penalise: trends that merely confirm existing brand identity without a new angle.
Compare against pillars: {pillar_names_str}. Name the pillar being confirmed OR extended.

5. CLIENT_SEGMENT_CLARITY (0–10)  weight: 0.05
Does this trend clearly map to a recognizable client type — without naming specific archetypes?
Score 8–10: clearly maps to ONE client type (e.g. occasion buyers, first-luxury buyers,
  investment collectors, self-reward buyers, gift buyers)
Score 5–7: broadly maps to a lifestyle without being specific
Score 1–4: so generic it applies to everyone; no differentiation

6. OCCASION_PURCHASE_TRIGGER (0–10)  weight: 0.05
Is this trend connected to a specific purchase occasion or life event?
Score 8–10: directly connected to proposal, anniversary, birthday, self-reward, gifting,
  graduation, milestone — check occasion_signal flag
Score 5–7: loosely connected to an occasion type
Score 1–4: purely aesthetic with no occasion trigger

NOTE: trend_velocity (weight 0.15) and evidence_credibility (weight 0.10) are computed
algorithmically from engagement recency and run_count. Do NOT score these yourself.

──────────────────────────────────────────────────────────────
COMPOSITE SCORE FORMULA (for reference — system recomputes with confidence weighting)
brand_engagement_depth×0.20 + client_touchpoint_specificity×0.20 + trend_velocity×0.15
+ vocabulary_transfer_potential×0.15 + intelligence_value×0.10 + evidence_credibility×0.10
+ client_segment_clarity×0.05 + occasion_purchase_trigger×0.05

SHORTLISTING CRITERIA
Shortlist ONLY if:
- client_touchpoint_specificity >= 4 (must give CA a genuine conversation reason)
- brand_engagement_depth >= 4 (must show real brand engagement, not generic luxury)
- All other LLM dimensions >= 3
- composite_score >= 6.5 (system will apply confidence weighting after)
- Genuinely actionable for {brand_name} CAs this week

──────────────────────────────────────────────────────────────
OUTPUT FORMAT

Return ONLY a valid JSON array — no markdown, no text outside the JSON.
One object per trend, same order as input batch:
[
  {{
    "trend_id": "string",
    "shortlist": true or false,
    "scores": {{
      "brand_engagement_depth": number,
      "client_touchpoint_specificity": number,
      "vocabulary_transfer_potential": number,
      "intelligence_value": number,
      "client_segment_clarity": number,
      "occasion_purchase_trigger": number
    }},
    "composite_score": number,
    "reasoning": "3-5 sentences. Must: (1) cite the most brand-specific snippet or signal flag; (2) explain what a CA could specifically say or do with this trend; (3) name the pillar confirmed or extended for intelligence_value; (4) note any celebrity/occasion/competitor signals found.",
    "confidence": "high" or "medium" or "low",
    "disqualifying_reason": null or "exact dimension that failed and why"
  }}
]"""
