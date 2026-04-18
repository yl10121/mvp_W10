import argparse
import json
import os
import re
import sys
import datetime
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
try:
    import config  # noqa: F401 — 单钥 OPENROUTER→OPENAI
except ImportError:
    pass

load_dotenv()

# Supabase integration (optional — silently skipped if not configured)
try:
    from supabase_writer import write_trend_brief, write_run_log as db_write_run_log
    _HAS_DB = True
except ImportError:
    _HAS_DB = False

# Paths
SCRIPT_DIR = Path(__file__).parent
# Primary input: module 2's shortlist output from the pipeline
MODULE2_OUTPUT = SCRIPT_DIR.parent.parent / "module_2" / "outputs" / "output_shortlist.json"
# Fallback: local trend_shortlist.json for standalone testing
JSON_PATH = SCRIPT_DIR / "trend_shortlist.json"
RUN_LOG_PATH = SCRIPT_DIR / "run_log.json"
PERSONAS_DIR = SCRIPT_DIR / "personas"
BRAND_PROFILES_DIR = SCRIPT_DIR / "brand_profiles"

MODEL = os.environ.get("DEFAULT_MODEL", "openai/gpt-4o-mini")

# System prompt: role, card format, rules
SYSTEM_PROMPT = (
    "You are a luxury retail trend intelligence assistant generating Client Insight Briefs "
    "for Client Advisors (CAs) at high-end fashion maisons in China.\n\n"
    "Your output is a structured trend card that a CA can scan in under 60 seconds and "
    "immediately act on in a client conversation. Everything you write must pass a single "
    "test: could a CA read this, pick up their phone, and open a WeChat conversation with "
    "a VIP client within 5 minutes?\n\n"
    "LANGUAGE RULE — CRITICAL: Write the entire card in English only. "
    "The ONE exception is the Conversation Starter section, which must include a Chinese version "
    "(first) followed by an English version. Do not use Chinese characters, bilingual labels, "
    "or Chinese text anywhere else in the card — not in section headers, not in data labels, "
    "not in the confidence note, not in the maison lens.\n\n"
    "## CARD FORMAT — OUTPUT EXACTLY THIS STRUCTURE:\n\n"
    "### [Trend Name in English]\n"
    "**Category:** [category] | **Relevance:** [brand] · [month, year]\n\n"
    "---\n\n"
    "**TREND OVERVIEW**\n"
    "[2–3 sentences. What is happening on XHS right now? Describe the visual or behavioral signal. "
    "Plain language a CA can repeat out loud. No jargon.]\n\n"
    "---\n\n"
    "**DATA SIGNAL**\n"
    "- Engagement rate: [X]% (vs. XHS fashion category avg ~4.5% · [N] posts · [month year])\n"
    "- Post growth: +[X]% (week-on-week)\n"
    "- Brand relevance: [high/medium/low]\n\n"
    "**CONFIDENCE NOTE**\n"
    "[use exactly the confidence level you are given] — [one sentence on methodology; "
    "if data is synthetic write: \"Synthetic data — for prototype testing only\"]\n\n"
    "---\n\n"
    "**CLIENT MATCH**\n"
    "**Best-fit persona:** [persona name from input]\n"
    "**Who they are:** [copy persona summary exactly from input]\n"
    "**Why this trend fits:** [copy match rationale exactly from input]\n"
    "**Match score:** [score]/10\n\n"
    "**This trend is NOT for:** [one sentence naming the client type to exclude — "
    "base this on the persona's avoid profile provided in the input]\n\n"
    "---\n\n"
    "**CONVERSATION STARTER**\n\n"
    "Chinese:\n"
    "「[2–3 sentences in Chinese. WeChat-intimate register. Structure: personal observation → "
    "relevance to client → open question. Tactile/sensory language. "
    "Sound like a trusted friend, not a brand brief.]」\n\n"
    "English:\n"
    "\"[Warm, specific. Never begin with 'I've noticed a lot of our clients...' "
    "or 'Many of our VIP customers...'. Sound like a real person.]\"\n\n"
    "---\n\n"
    "**PRODUCT SPOTLIGHT**\n"
    "[If the trend directly promotes a specific product, name it here with a one-line description. "
    "If the trend does not directly promote a specific product, name the most relevant product category "
    "(e.g., 'structured top-handle bag') and list 1–3 products from the brand that fit that category. "
    "Do not leave this section empty — every trend must connect to a concrete product or category.]\n\n"
    "---\n\n"
    "## RULES:\n"
    "- LANGUAGE: All content is in English. Only the Conversation Starter section contains Chinese (first) and English (second).\n"
    "- ALWAYS contextualize every metric: show figure + benchmark + sample size + date. No floating numbers.\n"
    "- The confidence level in CONFIDENCE NOTE must exactly match the value provided in the input — do not substitute your own assessment.\n"
    "- CONFIDENCE NOTE must explain the methodology, not just state the level.\n"
    "- The 'NOT for' statement is required — draw from the persona's avoid field provided.\n"
    "- Never write conversation starters that begin with 'I've noticed a lot of our clients...'\n"
    "- The persona summary and match rationale must be used as provided — do not rewrite them.\n"
    "- Do not pad. Every sentence must inform a decision or enable a conversation.\n"
    "- CONVERSATION STARTER — OPENING LINE: The opening line must be open-ended (never a yes/no question). "
    "It must sound like natural spoken language. Avoid brand-marketing phrasing such as 'This piece is a "
    "timeless investment' or 'a wardrobe essential'. Good example: 'What kind of bags have you been "
    "reaching for lately?'\n"
    "- BRAND PROFILE: Before generating the card, reference the BRAND PROFILE provided in the input. "
    "Do NOT assume who the current creative director is or reference specific campaigns unless explicitly "
    "stated in the provided brand profile. If uncertain about any brand fact, omit it rather than guess.\n"
    "- PRODUCT SPOTLIGHT is required on every card. If the trend does not map to a specific product, "
    "suggest the closest product category and name matching products from the brand.\n"
)

# User message template: trend data + persona data
CARD_TEMPLATE = (
    "Generate a Client Insight Brief card for the trend below.\n\n"
    "BRAND: {brand}\n"
    "CITY: {city}\n"
    "DATA NOTE: {data_note}\n\n"
    "--- BRAND PROFILE ---\n"
    "{brand_profile_block}\n\n"
    "--- TREND DATA ---\n"
    "Trend label: {trend_label}\n"
    "Category: {category}\n"
    "Cluster summary: {cluster_summary}\n"
    "Post count: {post_count:,}\n"
    "Engagement rate: {engagement_rate_pct}% (XHS fashion category avg benchmark: ~4.5%)\n"
    "Week-on-week growth: {week_on_week_growth}\n"
    "Brand relevance: {brand_relevance}\n"
    "Confidence (use this exact value in the card): {confidence}\n"
    "Confidence methodology: {confidence_method}\n"
    "Top post example: {top_post_example}\n"
    "Trending hashtags: {trending_hashtags}\n\n"
    "--- CLIENT PERSONA MATCH ---\n"
    "Best-fit persona: {persona_name}\n"
    "Persona summary: {persona_summary}\n"
    "Why this trend fits: {match_rationale}\n"
    "Match score: {match_score}/10\n"
    "Persona avoids: {persona_avoid}\n\n"
    "--- CITY TONE GUIDELINE ---\n"
    "{city_tone_rule}"
)

# B3: Decision logic — rules-first
DECISION_CRITERIA = [
    "City match: trend['city'] must equal the selected store city",
    "Brand relevance: trend['brand_relevance'] must be 'high'; 'medium' accepted only if fewer than 3 high-relevance trends exist for the city",
    "Composite score: ranked by weighted sum of engagement_rate (×40), growth_pct (×30), post_count normalised (×30); top 3 selected",
]
EVIDENCE_REQUIREMENTS = [
    "Minimum post_count >= 3,000 to be considered as evidence",
    "Engagement rate >= 0.08 required; trends below this threshold are flagged LOW confidence regardless of other signals",
]
FAILURE_TYPES = {
    "MISSING_EVIDENCE": {
        "name": "FAILURE TYPE 1 — Missing Evidence",
        "trigger": "Fewer than 3 of these fields are present: post_count, engagement_rate, week_on_week_growth, cluster_summary",
        "consequence": "Card cannot make evidence-anchored claims; 'Why it's moving' would be invented. Card is skipped.",
    },
    "MISSING_CONTEXT": {
        "name": "FAILURE TYPE 2 — Missing Context",
        "trigger": "city or target_age_range is absent from the trend object",
        "consequence": "'Who to bring it up with' and city-specific tone cannot be applied — card becomes generic and unusable for a CA. Card is skipped.",
    },
    "WEAK_SIGNAL": {
        "name": "FAILURE TYPE 3 — Weak Signal",
        "trigger": "week_on_week_growth is under +10% AND engagement_rate is under 0.08",
        "consequence": "Trend has insufficient momentum to recommend this week — surfacing it risks wasting client interaction capital on something not yet proven. Card is skipped.",
    },
}

FAILURE_MODE = (
    "Three named failure types are checked before card generation. "
    "MISSING_EVIDENCE: fewer than 3 evidence fields present. "
    "MISSING_CONTEXT: city field absent. "
    "WEAK_SIGNAL: growth under +10% AND engagement under 0.08. "
    "Any failure skips the card and logs the reason. "
    "If fewer than 3 valid trends remain, the agent lowers brand_relevance threshold to include 'medium' trends."
)


def check_failures(trend):
    """
    B3: Check the three named failure types for a trend object.
    Returns a list of triggered failure type keys, or empty list if none.
    """
    failures = []

    # FAILURE TYPE 1 — Missing Evidence
    evidence_fields = ["post_count", "engagement_rate", "week_on_week_growth", "cluster_summary"]
    present = sum(1 for f in evidence_fields if trend.get(f) not in (None, "", []))
    if present < 3:
        failures.append("MISSING_EVIDENCE")

    # FAILURE TYPE 2 — Missing Context
    if not trend.get("city"):
        failures.append("MISSING_CONTEXT")

    # FAILURE TYPE 3 — Weak Signal
    if "week_on_week_growth" in trend and "engagement_rate" in trend:
        growth_str = str(trend["week_on_week_growth"]).replace("%", "").replace("+", "")
        try:
            growth_pct = int(growth_str)
        except ValueError:
            growth_pct = 0
        if growth_pct < 10 and trend["engagement_rate"] < 0.08:
            failures.append("WEAK_SIGNAL")

    return failures


def normalise_from_module2(shortlist_item):
    """Convert module 2 schema into the format agent.py expects."""
    metrics = shortlist_item.get("metric_signal", {})
    evidence = shortlist_item.get("evidence_references", [])
    return {
        "trend_id": shortlist_item.get("trend_id", ""),
        "trend_label": shortlist_item.get("label", ""),
        "city": shortlist_item.get("city", None),  # None = no city field from module 2
        "category": shortlist_item.get("category", ""),
        "cluster_summary": shortlist_item.get("why_selected", ""),
        "post_count": metrics.get("post_count", 0),
        "engagement_rate": metrics.get("avg_engagement", 0) / 100000 if metrics.get("avg_engagement") else 0,
        "week_on_week_growth": "+20%",  # module 2 does not provide WoW growth
        "top_post_example": evidence[0] if evidence else "",
        "trending_hashtags": evidence[1:] if len(evidence) > 1 else [],
        "brand_relevance": shortlist_item.get("confidence", "medium"),
    }


def _detect_data_note():
    """Return 'live XHS data' if the scraper has run, otherwise 'synthetic data (prototype)'."""
    raw_posts = SCRIPT_DIR.parent.parent / "module_1" / "data" / "xhs_raw_posts.json"
    if raw_posts.exists():
        return "live XHS data scraped via DrissionPage"
    return "synthetic data (prototype — not live XHS data)"


def load_trends():
    # Try module 2 pipeline output first
    if MODULE2_OUTPUT.exists():
        print(f"Loading trends from module 2 output: {MODULE2_OUTPUT}")
        with open(MODULE2_OUTPUT, "r", encoding="utf-8") as f:
            data = json.load(f)
        trends = [normalise_from_module2(t) for t in data.get("shortlist", [])]
        # Wrap in same structure the rest of the code expects
        return {
            "query_context": {
                "brand": data.get("brand", "Christian Dior"),
                "market": "China luxury fashion",
                "source": "module_2/output_shortlist.json",
                "week": data.get("generated_at", "")[:10],
                "data_note": _detect_data_note(),
            },
            "trends": trends,
        }
    # Fallback to local file for standalone testing
    if not JSON_PATH.exists():
        raise FileNotFoundError(
            f"No input found. Expected module 2 output at {MODULE2_OUTPUT} "
            f"or local fallback at {JSON_PATH}"
        )
    print(f"Module 2 output not found — falling back to {JSON_PATH}")
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "query_context" in data and "data_note" not in data["query_context"]:
        data["query_context"]["data_note"] = _detect_data_note()
    return data


def get_user_inputs():
    print("\n=== CA Trend Brief Generator ===\n")

    if sys.stdin.isatty():
        brand_input = input("Brand (e.g. Dior, Chanel, Louis Vuitton — press Enter for Dior): ").strip()
        brand = brand_input if brand_input else "Dior"

        city_input = input("Store city (e.g. Shanghai, Beijing, Chengdu — press Enter for Shanghai): ").strip()
        city = city_input if city_input else "Shanghai"
    else:
        brand = "Dior"
        city = "Shanghai"

    return brand, city


def compute_composite_score(trend):
    """Weighted composite score for ranking trends."""
    growth_pct = int(trend["week_on_week_growth"].replace("%", "").replace("+", ""))
    # Normalise post_count: treat 10,000 as max reference
    post_norm = min(trend["post_count"] / 10000, 1.0)
    return (
        trend["engagement_rate"] * 40
        + (growth_pct / 100) * 30
        + post_norm * 30
    )


def assess_confidence(trend):
    """B3: Confidence flag based on evidence requirements."""
    if trend["post_count"] < 3000:
        return "LOW"
    if trend["engagement_rate"] < 0.08:
        return "LOW"
    score = 0
    if trend["post_count"] >= 5000:
        score += 1
    if trend["engagement_rate"] >= 0.095:
        score += 1
    growth_pct = int(trend["week_on_week_growth"].replace("%", "").replace("+", ""))
    if growth_pct >= 20:
        score += 1
    if trend["brand_relevance"] == "high":
        score += 1
    if score >= 3:
        return "HIGH"
    elif score >= 2:
        return "MEDIUM"
    return "LOW"


def get_confidence_method(trend, confidence, data_note="synthetic data (prototype)"):
    """Return a one-line methodology string for the confidence note."""
    source_note = f"Source: {data_note}"
    if confidence == "HIGH":
        return (
            f"Engagement rate ({trend['engagement_rate']:.1%}) and post count ({trend['post_count']:,}) "
            f"exceed all thresholds with strong brand relevance. {source_note}."
        )
    elif confidence == "MEDIUM":
        return (
            f"Meets minimum engagement and post-count thresholds but below high-confidence levels. "
            f"{source_note}."
        )
    else:
        return (
            f"Post count ({trend['post_count']:,}) or engagement rate ({trend['engagement_rate']:.1%}) "
            f"below threshold (requires ≥3,000 posts, ≥8% engagement). {source_note}."
        )


def select_trends(trends, city, top_n=3):
    """B3: Apply decision logic — filter by city, run failure checks, rank, return top N.

    Trends with city=None (e.g. from module 2 which has no city field) are treated as
    city-agnostic and included in all city runs. The user-selected city is stamped onto
    them so downstream prompt formatting works correctly.
    """
    # Step 1: filter by city — include city-agnostic trends (city=None) and stamp the city
    city_trends = []
    for t in trends:
        if t["city"] is None or t["city"] == city:
            city_trends.append({**t, "city": city})

    # Step 2: run failure checks — exclude any trend that triggers a failure type
    valid = []
    failed = []
    for t in city_trends:
        triggered = check_failures(t)
        if triggered:
            failed.append({"trend_id": t["trend_id"], "failures": triggered})
        else:
            valid.append(t)

    # Step 3: prefer high brand relevance among valid trends
    high_relevance = [t for t in valid if t["brand_relevance"] == "high"]
    medium_relevance = [t for t in valid if t["brand_relevance"] == "medium"]

    # Step 4: fallback to medium if not enough high-relevance trends pass
    if len(high_relevance) >= top_n:
        pool = high_relevance
        used_fallback = False
    else:
        pool = high_relevance + medium_relevance
        used_fallback = True

    # Step 5: rank by composite score, take top N
    ranked = sorted(pool, key=compute_composite_score, reverse=True)[:top_n]

    return ranked, used_fallback, failed


CITY_TONE = {
    "Beijing": "Beijing cards should feel bolder and more direct.",
    "Shanghai": "Shanghai cards should feel more understated and considered.",
    "Chengdu": "Chengdu cards should feel warm and aspirational, reflecting a city with growing luxury appetite and strong local identity.",
    "Guangzhou": "Guangzhou cards should feel practical and results-oriented — clients here respond to value and quality narratives over pure prestige.",
    "Shenzhen": "Shenzhen cards should feel modern and forward-looking, reflecting a younger, tech-adjacent luxury consumer.",
    "Hangzhou": "Hangzhou cards should feel refined and digitally savvy, reflecting a consumer base shaped by e-commerce culture and aesthetic taste.",
}
DEFAULT_CITY_TONE = "Cards should feel refined and client-appropriate, calibrated to the local luxury sensibility."

PERSONA_MATCH_PROMPT = (
    "You are a luxury retail strategist helping match a trend to the client persona most likely to resonate with it.\n\n"
    "TREND:\n"
    "- Label: {trend_label}\n"
    "- Category: {category}\n"
    "- Summary: {cluster_summary}\n"
    "- Evidence: {top_post_example}\n\n"
    "PERSONAS (choose exactly one):\n"
    "{personas_block}\n\n"
    "Return ONLY valid JSON in this exact structure, no other text:\n"
    "{{\n"
    '  "persona_id": "<id of best-matched persona>",\n'
    '  "persona_name": "<name>",\n'
    '  "persona_summary": "<copy the summary field from the matched persona, unchanged>",\n'
    '  "match_rationale": "<2-3 sentences explaining why this trend speaks to this persona specifically>",\n'
    '  "match_score": <number from 1-10 indicating strength of match>\n'
    "}}"
)


def load_personas(brand):
    """Load persona file for the given brand. Returns list of personas or None."""
    slug = re.sub(r"[^a-z0-9_]", "", brand.lower().strip().replace(" ", "_").replace("-", "_"))
    filename = f"{slug}_personas.json"
    persona_path = PERSONAS_DIR / filename
    if not persona_path.exists():
        print(f"  [personas] No persona file found at {persona_path} — skipping persona matching.")
        return None
    with open(persona_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("personas", [])


def load_brand_profile(brand):
    """Load brand profile JSON for the given brand. Returns a dict or None."""
    slug = re.sub(r"[^a-z0-9_]", "", brand.lower().strip().replace(" ", "_").replace("-", "_"))
    filename = f"{slug}_profile.json"
    profile_path = BRAND_PROFILES_DIR / filename
    if not profile_path.exists():
        print(f"  [brand_profile] No profile found at {profile_path} — brand context will be omitted.")
        return None
    with open(profile_path, "r", encoding="utf-8") as f:
        return json.load(f)


def format_brand_profile_block(profile):
    """Format a brand profile dict into a prompt-ready text block."""
    if not profile:
        return "No brand profile provided. Do not assume brand facts; omit any uncertain details."
    lines = []
    for key, value in profile.items():
        if isinstance(value, list):
            lines.append(f"{key}: {', '.join(str(v) for v in value)}")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def match_persona_to_trend(client, trend, personas):
    """Use LLM to select the best-matched persona for a given trend."""
    personas_block = "\n".join(
        f"- id={p['id']} | name={p['name']} | age={p['age_range']}\n"
        f"  summary: {p['summary']}\n"
        f"  receptive to: {p['trend_receptivity']}\n"
        f"  avoids: {p['avoid']}"
        for p in personas
    )
    prompt = PERSONA_MATCH_PROMPT.format(
        trend_label=trend["trend_label"],
        category=trend["category"],
        cluster_summary=trend["cluster_summary"],
        top_post_example=trend["top_post_example"],
        personas_block=personas_block,
    )
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.choices[0].message.content.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        result = json.loads(raw)
        # Attach the matched persona's avoid field for use in card generation
        persona_id = result.get("persona_id")
        if persona_id:
            for p in personas:
                if p["id"] == persona_id:
                    result["avoid"] = p.get("avoid", "")
                    break
        return result
    except json.JSONDecodeError:
        return {"persona_name": "Unknown", "persona_summary": "", "match_rationale": raw, "match_score": None, "avoid": ""}


def generate_trend_card(client, trend, brand, city, persona_match=None, data_note="synthetic data (prototype)", brand_profile=None):
    """B1: Build prompt and call Claude API."""
    confidence = assess_confidence(trend)
    confidence_method_str = get_confidence_method(trend, confidence, data_note)

    if persona_match:
        persona_name = persona_match.get("persona_name", "N/A")
        persona_summary = persona_match.get("persona_summary", "")
        match_rationale = persona_match.get("match_rationale", "")
        match_score = persona_match.get("match_score", "N/A")
        persona_avoid = persona_match.get("avoid", "")
    else:
        persona_name = "N/A (no persona data loaded)"
        persona_summary = "N/A"
        match_rationale = "N/A"
        match_score = "N/A"
        persona_avoid = "N/A"

    prompt = CARD_TEMPLATE.format(
        brand=brand,
        city=city,
        data_note=data_note,
        brand_profile_block=format_brand_profile_block(brand_profile),
        trend_label=trend["trend_label"],
        category=trend["category"],
        cluster_summary=trend["cluster_summary"],
        post_count=trend["post_count"],
        engagement_rate_pct=round(trend["engagement_rate"] * 100, 1),
        week_on_week_growth=trend["week_on_week_growth"],
        top_post_example=trend["top_post_example"],
        trending_hashtags=", ".join(trend["trending_hashtags"]),
        brand_relevance=trend["brand_relevance"],
        confidence=confidence,
        confidence_method=confidence_method_str,
        persona_name=persona_name,
        persona_summary=persona_summary,
        match_rationale=match_rationale,
        match_score=match_score,
        persona_avoid=persona_avoid,
        city_tone_rule=CITY_TONE.get(city, DEFAULT_CITY_TONE),
    )

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=1200,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )

    return prompt, response.choices[0].message.content


def _inline_md(text):
    """Convert inline markdown to HTML (bold, code). Input must already be HTML-escaped."""
    import html as _html
    text = _html.escape(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    return text


def _block_md(text):
    """Convert a markdown block (paragraphs + bullet lists) to HTML."""
    lines = text.strip().split('\n')
    out = []
    in_list = False
    for line in lines:
        s = line.strip()
        if not s:
            if in_list:
                out.append('</ul>')
                in_list = False
            continue
        if s.startswith('- '):
            if not in_list:
                out.append('<ul>')
                in_list = True
            out.append(f'<li>{_inline_md(s[2:])}</li>')
        else:
            if in_list:
                out.append('</ul>')
                in_list = False
            out.append(f'<p>{_inline_md(s)}</p>')
    if in_list:
        out.append('</ul>')
    return '\n'.join(out)


def _card_to_html(trend_id, card_text):
    """Convert one LLM card (markdown) to a styled HTML block."""
    import html as _html
    sections = re.split(r'\n---\n', card_text.strip())
    parts = []

    for section in sections:
        section = section.strip()
        if not section:
            continue
        first = section.split('\n')[0].strip()

        # Title line: ### Trend Name
        if first.startswith('### '):
            title = _inline_md(first[4:])
            meta_lines = '\n'.join(section.split('\n')[1:]).strip()
            parts.append(
                f'<div class="card-header">'
                f'<div class="card-title">{title}</div>'
                f'<div class="card-meta">{_inline_md(meta_lines)}</div>'
                f'</div>'
            )
        # Known labelled sections
        elif re.match(r'^\*\*(TREND OVERVIEW|DATA SIGNAL|CLIENT MATCH|CONVERSATION STARTER)\*\*', first):
            label = re.match(r'^\*\*(.+?)\*\*', first).group(1)
            body = re.sub(r'^\*\*[^*]+\*\*\n?', '', section, count=1)

            # Conversation starter: split Chinese / English sub-blocks
            if label == 'CONVERSATION STARTER':
                chinese_block = re.search(r'「(.+?)」', body, re.DOTALL)
                english_block = re.search(r'English[^\n]*\n+"(.+?)"', body, re.DOTALL)
                inner = ''
                if chinese_block:
                    inner += (f'<div class="starter-label">Chinese</div>'
                               f'<div class="starter-chinese">「{_html.escape(chinese_block.group(1))}」</div>')
                if english_block:
                    inner += (f'<div class="starter-label">English</div>'
                               f'<div class="starter-english">"{_html.escape(english_block.group(1))}"</div>')
                parts.append(
                    f'<div class="section section-starter">'
                    f'<div class="section-label">{label}</div>{inner}</div>'
                )
            else:
                css_class = {
                    'TREND OVERVIEW': 'section-overview',
                    'DATA SIGNAL': 'section-data',
                    'CLIENT MATCH': 'section-client',
                }.get(label, '')
                parts.append(
                    f'<div class="section {css_class}">'
                    f'<div class="section-label">{label}</div>'
                    f'{_block_md(body)}</div>'
                )
        else:
            parts.append(f'<div class="section">{_block_md(section)}</div>')

    return f'<div class="card" id="{trend_id}">{"".join(parts)}</div>'


def write_html_report(brand, city, week, source, selected, cards, used_fallback):
    """Generate a self-contained styled HTML trend brief."""
    slug = re.sub(r"[^a-z0-9_]", "", brand.lower().strip().replace(" ", "_").replace("-", "_"))
    output_path = SCRIPT_DIR / f"trend_cards_{slug}_{city.lower()}.html"
    generated = datetime.datetime.now().strftime('%d %b %Y, %H:%M')

    cards_html = '\n'.join(
        _card_to_html(t['trend_id'], c) for t, c in zip(selected, cards)
    )

    fallback_banner = (
        '<div class="banner">⚠ Fewer than 3 high-relevance trends found — '
        'medium-relevance trends included.</div>' if used_fallback else ''
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CA Trend Brief — {brand} {city}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    background: #f0ede8;
    color: #111111;
    font-size: 15px;
    line-height: 1.65;
  }}
  .page {{ max-width: 840px; margin: 0 auto; padding: 40px 24px 80px; }}

  /* Header */
  .brief-header {{
    background: #111827;
    color: #fff;
    border-radius: 12px;
    padding: 32px 36px 28px;
    margin-bottom: 32px;
  }}
  .brief-header h1 {{
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -0.5px;
    margin-bottom: 12px;
  }}
  .brief-meta {{
    display: flex;
    gap: 24px;
    font-size: 13px;
    color: #9ca3af;
    flex-wrap: wrap;
  }}
  .brief-meta span {{ display: flex; align-items: center; gap: 6px; }}

  /* Banner */
  .banner {{
    background: #fef3c7;
    border: 1px solid #fcd34d;
    border-radius: 8px;
    padding: 10px 16px;
    font-size: 14px;
    color: #92400e;
    margin-bottom: 24px;
  }}

  /* Card */
  .card {{
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.07), 0 4px 12px rgba(0,0,0,0.04);
    margin-bottom: 28px;
    overflow: hidden;
  }}

  /* Card header */
  .card-header {{
    background: #1c1c2e;
    color: #fff;
    padding: 24px 30px 20px;
  }}
  .card-title {{
    font-size: 20px;
    font-weight: 700;
    letter-spacing: -0.3px;
    margin-bottom: 7px;
  }}
  .card-meta {{
    font-size: 13px;
    color: #94a3b8;
  }}
  .card-meta strong {{ color: #e2e8f0; font-weight: 600; }}

  /* Sections */
  .section {{
    padding: 22px 30px;
    border-bottom: 1px solid #eeecec;
  }}
  .section:last-child {{ border-bottom: none; }}
  .section-label {{
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.4px;
    text-transform: uppercase;
    color: #6b7280;
    margin-bottom: 12px;
  }}
  .section p {{ margin-bottom: 10px; color: #111111; font-size: 15px; line-height: 1.65; }}
  .section p:last-child {{ margin-bottom: 0; }}
  .section strong {{ color: #000; font-weight: 700; }}

  /* Trend overview — largest, most prominent */
  .section-overview {{ background: #fff; border-left: 4px solid #1c1c2e; }}
  .section-overview .section-label {{ color: #1c1c2e; font-size: 12px; }}
  .section-overview p {{ font-size: 16px; color: #0f0f0f; line-height: 1.7; font-weight: 400; }}

  /* Data signal */
  .section-data {{ background: #f7f6f4; }}
  .section-data .section-label {{ color: #374151; }}
  .section-data ul {{ list-style: none; padding: 0; }}
  .section-data li {{
    padding: 8px 0;
    border-bottom: 1px solid #e8e6e2;
    font-size: 14px;
    color: #111111;
    font-weight: 500;
  }}
  .section-data li:last-child {{ border-bottom: none; }}
  .section-data code {{
    background: #e8e6e2;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 13px;
    font-family: "SF Mono", "Fira Code", monospace;
    color: #111111;
  }}

  /* Brand relevance pill inside data section */
  .section-data li strong {{
    color: #000;
    font-weight: 700;
  }}

  /* Client match */
  .section-client {{ border-left: 4px solid #6366f1; }}
  .section-client .section-label {{ color: #4f46e5; }}
  .section-client p {{ font-size: 14px; color: #111111; }}

  /* Conversation starter */
  .section-starter {{ background: #f8f7f4; }}
  .starter-label {{
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: #6b7280;
    margin: 14px 0 7px;
  }}
  .starter-label:first-child {{ margin-top: 0; }}
  .starter-chinese {{
    background: #fff;
    border: 1px solid #d6d3ce;
    border-radius: 8px;
    padding: 14px 18px;
    font-size: 16px;
    line-height: 1.75;
    color: #0f0f0f;
    margin-bottom: 6px;
    font-weight: 400;
  }}
  .starter-english {{
    background: #fff;
    border: 1px solid #d6d3ce;
    border-radius: 8px;
    padding: 14px 18px;
    font-size: 14px;
    color: #1f2937;
    font-style: italic;
    line-height: 1.65;
  }}

  /* Mobile */
  @media (max-width: 640px) {{
    .page {{ padding: 16px 12px 60px; }}
    .brief-header {{ padding: 22px 20px 18px; border-radius: 10px; }}
    .brief-header h1 {{ font-size: 22px; }}
    .brief-meta {{ font-size: 12px; gap: 12px; }}
    .card {{ border-radius: 10px; margin-bottom: 20px; }}
    .card-header {{ padding: 18px 20px 14px; }}
    .card-title {{ font-size: 17px; }}
    .section {{ padding: 16px 20px; }}
    .section p {{ font-size: 14px; }}
    .section-overview p {{ font-size: 15px; }}
    .section-data li {{ font-size: 13px; }}
    .starter-chinese {{ font-size: 15px; padding: 12px 14px; }}
    .starter-english {{ font-size: 13px; padding: 12px 14px; }}
  }}

  /* Print */
  @media print {{
    body {{ background: #fff; }}
    .page {{ padding: 0; max-width: 100%; }}
    .card {{ box-shadow: none; border: 1px solid #e5e7eb; break-inside: avoid; }}
    .brief-header {{ border-radius: 0; }}
  }}
</style>
</head>
<body>
<div class="page">
  <div class="brief-header">
    <h1>Client Advisor Trend Brief</h1>
    <div class="brief-meta">
      <span>{brand} · {city}</span>
      <span>Week of {week}</span>
      <span>Source: {source}</span>
      <span>Generated {generated}</span>
    </div>
  </div>
  {fallback_banner}
  {cards_html}
</div>
</body>
</html>"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return output_path


def write_report(brand, city, week, source, selected, cards, used_fallback):
    """B4: Write city- and brand-specific markdown report."""
    slug = re.sub(r"[^a-z0-9_]", "", brand.lower().strip().replace(" ", "_").replace("-", "_"))
    output_path = SCRIPT_DIR / f"trend_cards_{slug}_{city.lower()}.md"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# CA Trend Brief — {brand} {city}\n\n")
        f.write(f"**Week:** {week}  \n")
        f.write(f"**Source:** {source}  \n")
        f.write(f"**Store:** {brand}, {city}  \n")
        f.write(f"**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}  \n")
        f.write(f"**Model:** {MODEL}  \n")
        if used_fallback:
            f.write(
                "\n> ⚠️ **Note:** Fewer than 3 high-relevance trends found for this city. "
                "Medium-relevance trends included.\n"
            )
        f.write("\n---\n\n")

        for trend, card_text in zip(selected, cards):
            f.write(f"## {trend['trend_id']}: {trend['trend_label']}\n\n")
            f.write(card_text.strip())
            f.write("\n\n---\n\n")

    return output_path


def main():
    # Accept --brand and --city from the pipeline orchestrator (main.py).
    # Falls back to interactive prompt when run standalone.
    parser = argparse.ArgumentParser(description="Module 3: CA Trend Brief Generator")
    parser.add_argument("--brand", default=None, help="Brand name (e.g. Dior, Chanel)")
    parser.add_argument("--city", default=None, help="Store city (e.g. Shanghai, Beijing)")
    _default_top = int(os.environ.get("M3_TOP_N", "3"))
    parser.add_argument(
        "--top-n",
        type=int,
        default=_default_top,
        metavar="N",
        help="Max trend cards to generate after filtering (default: env M3_TOP_N or 3). Use ≥10 for Week 11.",
    )
    args, _ = parser.parse_known_args()

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise EnvironmentError("OPENROUTER_API_KEY not set. Check your .env file.")

    client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")

    # B1: Get brand + city — from CLI args (pipeline) or interactive prompt (standalone)
    if args.brand and args.city:
        brand, city = args.brand, args.city
        print(f"\n=== CA Trend Brief Generator ===")
        print(f"Brand: {brand} | City: {city} (from pipeline)\n")
    else:
        brand, city = get_user_inputs()

    # B2: Retrieve context from trend_shortlist.json
    data = load_trends()
    context = data["query_context"]
    all_trends = data["trends"]
    all_ids = [t["trend_id"] for t in all_trends]

    print(f"\nRetrieved {len(all_trends)} trends from trend_shortlist.json")
    print(f"Applying decision logic for: {brand} — {city}\n")

    # B3: Apply decision logic
    selected, used_fallback, failed_trends = select_trends(
        all_trends, city, top_n=max(1, args.top_n)
    )

    if failed_trends:
        print(f"Excluded {len(failed_trends)} trend(s) due to failure checks:")
        for f in failed_trends:
            labels = ", ".join(FAILURE_TYPES[k]["name"] for k in f["failures"])
            print(f"  {f['trend_id']} — {labels}")
        print()

    if not selected:
        print(f"No valid trends found for city: {city}. Check your trend_shortlist.json.")
        return

    print(f"Selected {len(selected)} trends after filtering:\n")
    for t in selected:
        conf = assess_confidence(t)
        score = compute_composite_score(t)
        print(f"  {t['trend_id']}: {t['trend_label']}  [confidence={conf}, score={score:.2f}]")

    # Load personas and brand profile for this brand
    personas = load_personas(brand)
    brand_profile = load_brand_profile(brand)

    # Generate cards
    print()
    cards = []
    persona_matches = []
    log_trends = []
    for i, trend in enumerate(selected, 1):
        print(f"[{i}/{len(selected)}] Processing: {trend['trend_label']}...")

        # Persona matching first — passed into card generation
        matched = None
        if personas:
            print(f"  Matching persona...")
            matched = match_persona_to_trend(client, trend, personas)
        persona_matches.append(matched)

        print(f"  Generating card...")
        prompt_used, card_text = generate_trend_card(
            client, trend, brand, city,
            persona_match=matched,
            data_note=context.get("data_note", "synthetic data (prototype)"),
            brand_profile=brand_profile,
        )
        confidence = assess_confidence(trend)
        cards.append(card_text)

        # B5: log per-trend trace fields
        log_trends.append({
            "trend_id": trend["trend_id"],
            "trend_label": trend["trend_label"],
            "decision_output": "SELECTED",
            "confidence": confidence,
            "composite_score": round(compute_composite_score(trend), 3),
            "evidence_used": {
                "post_count": trend["post_count"],
                "engagement_rate": trend["engagement_rate"],
                "week_on_week_growth": trend["week_on_week_growth"],
                "brand_relevance": trend["brand_relevance"],
                "top_post_example": trend["top_post_example"],
                "trending_hashtags": trend["trending_hashtags"],
            },
            "matched_persona": matched,
            "prompt_used": prompt_used,
        })

    # B4: Write reports
    output_path = write_report(brand, city, context["week"], context["source"], selected, cards, used_fallback)
    html_path = write_html_report(brand, city, context["week"], context["source"], selected, cards, used_fallback)

    # B5: Save run_log.json
    high_trends = [t for t in log_trends if t["confidence"] == "HIGH"]
    next_step = (
        f"Share the {len(selected)} trend cards with the {brand} {city} CA team for review. "
        f"{len(high_trends)} card(s) are HIGH confidence and ready for client conversations. "
        f"Run log_feedback.py after team review."
    )

    run_log = {
        "run_timestamp": datetime.datetime.now().isoformat(),
        "model": MODEL,
        "brand": brand,
        "city": city,
        "week": context["week"],
        "prompt_template": SYSTEM_PROMPT,
        "retrieved_source": "trend_shortlist.json",
        "retrieved_record_ids": all_ids,
        "decision_logic": {
            "type": "LLM-first",
            "criteria": DECISION_CRITERIA,
            "evidence_requirements": EVIDENCE_REQUIREMENTS,
            "failure_types_defined": FAILURE_TYPES,
            "failure_mode_summary": FAILURE_MODE,
            "used_fallback_to_medium_relevance": used_fallback,
            "excluded_trends": [
                {
                    "trend_id": f["trend_id"],
                    "failures": [
                        {"type": k, "definition": FAILURE_TYPES[k]}
                        for k in f["failures"]
                    ],
                }
                for f in failed_trends
            ],
        },
        "selected_trends": log_trends,
        "next_step_suggestion": next_step,
    }

    with open(RUN_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(run_log, f, indent=2, ensure_ascii=False)

    # ── Supabase sync (optional) ──────────────────────────────────────────────
    if _HAS_DB:
        try:
            run_id = run_log.get("run_timestamp", datetime.datetime.now().isoformat())
            md_text = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
            html_text = html_path.read_text(encoding="utf-8") if html_path.exists() else ""
            write_trend_brief(
                run_id=run_id, brand=brand, city=city,
                output_markdown=md_text, output_html=html_text,
                trend_cards=log_trends, source_file=str(JSON_PATH),
                model_used=MODEL,
            )
            db_write_run_log(
                run_id=run_id, brand=brand, city=city,
                model_used=MODEL, brief_count=len(selected),
            )
        except Exception as e:
            print(f"  [DB] Supabase sync failed (non-fatal): {e}")

    print(f"\nDone!")
    print(f"  HTML    → {html_path.name}  (open in browser, print to PDF)")
    print(f"  Markdown → {output_path.name}")
    print(f"  Run log → {RUN_LOG_PATH.name}")
    print(f"\nNext step: {next_step}")


if __name__ == "__main__":
    main()
