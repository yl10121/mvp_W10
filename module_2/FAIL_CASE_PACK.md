# Module 2 — Fail Case Pack (Week 11)

## Bad Output Example

- **Trend ID:** run_0017_t07
- **Label:** CELINE 26 Summer Men's Relaxed Jackets
- **Composite Score:** 3.65
- **Run ID:** m2_20260411_060252
- **Reasoning from eval:** client_persona_match — lacks deep resonance with archetypes. No archetype matched. client_persona_match: 3, ca_conversational_utility: 4, novelty: 3.

---

## Why It Failed (one sentence)

This trend failed because the menswear relaxed jacket content had no meaningful connection to any of Celine's three client archetypes — all of whom are female-coded in lifestyle and aspiration — resulting in a client_persona_match score of 3 and a composite score of 3.65, well below the 6.5 shortlist threshold.

---

## Fix We Will Try Next Week (one sentence)

Add a pre-filter rule that rejects real XHS trends where the label or summary contains menswear-only signals (e.g. "men's", "menswear", "男装") unless the brand profile explicitly lists menswear as an active category, preventing gender-mismatched content from reaching LLM evaluation entirely.
