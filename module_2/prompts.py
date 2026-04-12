"""
prompts.py — LLM prompt templates for Module 2 Trend Relevance & Materiality Filter Agent.

Brand name and profile details are injected at runtime.
Week 11: prompts now explicitly reference client archetypes by name,
hero products by name, and aesthetic pillars by name.
"""

import json


def build_system_prompt(brand_profile: dict) -> str:
    brand_name = brand_profile.get("brand_name", "the brand")
    aesthetic = brand_profile.get("aesthetic_dna", brand_profile.get("aesthetic", "luxury"))
    clientele = brand_profile.get("clientele", "affluent clients")
    tone = brand_profile.get("clienteling_tone", "precise, expert, refined")
    voice = brand_profile.get("brand_voice", "spare and confident")
    director = brand_profile.get("current_creative_director", "")
    director_str = f" under {director}" if director else ""

    archetypes = brand_profile.get("client_archetypes", [])
    archetype_names = [a.get("name", "") for a in archetypes]
    archetype_str = ", ".join(archetype_names) if archetype_names else "the brand's target client"

    return (
        f"You are a senior luxury retail trend analyst specialising in Chinese consumer behaviour "
        f"on Xiaohongshu, with deep expertise in {brand_name}{director_str}. "
        f"You evaluate trend signals and decide which trends are truly material, brand-appropriate, "
        f"and actionable for {brand_name} Client Advisors in Shanghai. "
        f"You are evidence-grounded and precise. "
        f"\n\n"
        f"{brand_name} aesthetic: {aesthetic}. "
        f"Target clientele: {clientele}. "
        f"Three client archetypes to keep in mind: {archetype_str}. "
        f"Clienteling tone: {tone}. "
        f"Brand voice: {voice}. "
        f"\n\n"
        f"You never shortlist a trend just because it is popular — it must reflect {brand_name}'s "
        f"specific aesthetic, match at least one named client archetype, and be genuinely usable "
        f"in a {brand_name} CA conversation within the next 7 days. "
        f"You always cite specific snippets or metrics in your reasoning. "
        f"You never write generic statements like 'this aligns with {brand_name} values' "
        f"without explaining exactly why with specific evidence from the trend object."
    )


def build_batch_evaluation_prompt(
    brand_profile: dict,
    trend_objects: list,
    today: str = "2026-03-25",
) -> str:
    """
    Build a batch evaluation prompt for up to 5 trend objects.
    Explicitly references client archetypes by name, hero products by name,
    and aesthetic pillars by name so the LLM uses them in scoring.
    """
    brand_name = brand_profile.get("brand_name", "the brand")

    # ── Client archetypes block ────────────────────────────────────────────────
    archetypes = brand_profile.get("client_archetypes", [])
    if archetypes:
        archetype_lines = []
        for a in archetypes:
            archetype_lines.append(
                f"  • {a['name']} ({a.get('age_range', '')}): {a.get('lifestyle', '')} "
                f"| Responds to: {a.get('trend_language_that_resonates', '')} "
                f"| Would never buy: {a.get('what_they_would_never_buy', '')}"
            )
        archetype_block = (
            "CLIENT ARCHETYPES (use these exact names in client_persona_match scoring):\n"
            + "\n".join(archetype_lines)
        )
    else:
        archetype_block = ""

    archetype_names = [a.get("name", "") for a in archetypes]
    archetype_names_str = ", ".join(archetype_names) if archetype_names else "the target client"

    # ── Hero products block ────────────────────────────────────────────────────
    hero_products = brand_profile.get("hero_products", {})
    if hero_products:
        hero_lines = []
        if isinstance(hero_products, dict):
            for cat, items in hero_products.items():
                if isinstance(items, list):
                    hero_lines.append(
                        f"  {cat.replace('_', ' ').title()}: {', '.join(items)}"
                    )
        hero_block = (
            "CURRENT HERO PRODUCTS "
            "(reference these specifically in ca_conversational_utility scoring):\n"
            + "\n".join(hero_lines)
        )
    else:
        hero_block = ""

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

    # ── Competitive differentiation note ──────────────────────────────────────
    competitive = brand_profile.get("competitive_differentiation", {})
    if competitive:
        comp_lines = [
            f"  vs {k.replace('_', ' ')}: {v}" for k, v in competitive.items()
        ]
        comp_note = "COMPETITIVE POSITIONING:\n" + "\n".join(comp_lines)
    else:
        comp_note = ""

    trends_str = json.dumps(trend_objects, ensure_ascii=False, indent=2)

    return f"""You are evaluating a batch of trend objects for {brand_name}.

Today's date: {today}

{archetype_block}

{hero_block}

{pillar_block}

{comp_note}

Trend Objects (batch of {len(trend_objects)}):
{trends_str}

──────────────────────────────────────────────────────────────
SCORING INSTRUCTIONS

For EACH trend object, score it on the 6 LLM dimensions below (0–10 each).
For EVERY score you must cite specific evidence — a snippet, a metric, a keyword, a date. No generic reasoning.

DIMENSIONS:

1. BRAND_FIT (0–10)
Does this trend match {brand_name}'s aesthetic DNA? Does it fit the clientele profile? Would a {brand_name} CA feel genuinely comfortable raising it in a client conversation? Cite a specific snippet or metric.

2. CA_CONVERSATIONAL_UTILITY (0–10)
Can a {brand_name} CA use this trend in a real client conversation within the next 7 days?

IMPORTANT: Check whether the trend object includes an "extracted_product" field. This means a specific product name was found organically mentioned in the real XHS posts — it is the most reliable signal for CA utility.
- If "extracted_product" is present: reference it directly in your reasoning AND in hero_product_link. This product was mentioned by real consumers so a CA can confidently open with it.
- If "extracted_product" is NOT present: do NOT invent a product name. Use hero_product_link only if you can genuinely infer the product from the trend content. Leave hero_product_link as null if unsure.

Score 8–10: trend has an extracted_product (organically mentioned in posts), OR strongly and unmistakably implies a specific named {brand_name} hero product.
Score 6–7: trend is clearly and obviously linkable to a {brand_name} product category even without naming a specific piece — e.g. a trend about quiet luxury tailoring maps obviously to ready-to-wear; a trend about investment bag aesthetics maps obviously to leather goods. No stretch required.
Score 4–5: trend is brand-relevant and the CA could connect it to a product category with some effort and context-setting — the link is real but not immediate.
Score 1–3: trend is purely aesthetic or abstract with no plausible product category connection at all.

3. LANGUAGE_SPECIFICITY (0–10)
Are the XHS evidence snippets using specific, vivid, quotable Chinese language a CA could naturally echo to a client?
Score 8–10: snippets contain specific emotional or cultural references that feel authentic and reusable. Quote the most specific snippet.
Score 1–4: snippets use generic luxury descriptors with no distinctive voice.

4. CLIENT_PERSONA_MATCH (0–10)
Based on the 3 client archetypes ({archetype_names_str}), how strongly does this trend resonate with at least one of them?
You MUST name the archetype in matched_archetype field (e.g. "独立新贵 Dúlì Xīnguì").
Score 8–10: extremely strong match — you can explain exactly why this archetype would respond.
Score 1–4: does not match any archetype's language, lifestyle, or aspiration.

5. NOVELTY (0–10)
Is this trend saying something genuinely new about how people engage with {brand_name}?
Compare against the 4 pillars: {pillar_names_str}.
If the trend purely confirms an existing pillar without adding a new specific angle, score 1–4.
If it offers a new specific cultural insight or product usage pattern not captured in existing pillars, score 7–10.
Name the pillar being confirmed or extended in matched_pillar field.

6. CATEGORY_FIT (0–10)
Is this trend appropriate for this specific product category? Ready-to-wear moves fast (recency matters most). Leather goods moves medium (sustained signal across weeks matters more). Cite the category and explain.

NOTE: trend_velocity and cross_run_persistence will be computed and added by the system from engagement_recency_pct and run_count on each trend object. Do NOT score these yourself.

──────────────────────────────────────────────────────────────
COMPOSITE SCORE FORMULA (for reference only — system will recompute)
brand_fit×0.20 + ca_conversational_utility×0.20 + trend_velocity×0.15 + language_specificity×0.15 + client_persona_match×0.10 + novelty×0.10 + category_fit×0.05 + cross_run_persistence×0.05

SHORTLISTING CRITERIA
Shortlist ONLY if:
- All 6 LLM-scored dimensions >= 4
- You judge it genuinely usable for {brand_name} CAs right now

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
      "client_persona_match": number,
      "novelty": number,
      "category_fit": number
    }},
    "matched_archetype": "exact archetype name from the list above, or null",
    "matched_pillar": "name of the aesthetic pillar this trend confirms or extends, or null",
    "hero_product_link": "specific hero product name the CA could reference, or null",
    "composite_score": number,
    "reasoning": "4-6 sentences. Must name the matched archetype, name a specific hero product if ca_conversational_utility >= 7, name the pillar being confirmed or extended, and cite at least one snippet or metric.",
    "confidence": "high" or "medium" or "low",
    "evidence_references": ["direct quote or metric from the trend object"],
    "disqualifying_reason": null or "exact dimension that failed and why — include archetype mismatch explanation if client_persona_match is the failure"
  }}
]"""
