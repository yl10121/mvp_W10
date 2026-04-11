# Module 2 — Evaluation Report

**Run ID:** m2_20260411_060252  
**Generated at:** 2026-04-11T06:02:52.274733+00:00  
**Brand:** Celine

---

## Batch Composition

| Source | Count |
|--------|-------|
| Real XHS (luxury_fashion) | 69 |
| Synthetic (luxury_fashion) | 0 |
| Beauty runs skipped | 40 |
| **Total input to filter** | **69** |

---

## Filter Results

- Pre-filter rejected: **30**
- Passed to LLM: **34**
- Shortlisted: **4**
- Noise reduction rate: **94.2%**

---

## Quality Checks

### 1. Off-Brand Rate
- Off-brand count: 1 (1.4% of input)
  - Taboo keyword rejections: 0
  - LLM brand_fit < 5: 1

### 2. Explanation Specificity (LLM confidence breakdown)
- High: 15 (44.1%)
- Medium: 19 (55.9%)
- Low: 0 (0.0%)

### 3. Noise Reduction
- 94.2% of input trends were filtered before reaching the shortlist.

### 4. New Dimensions (Week 11)
- **CA Conversational Utility**: % of shortlisted trends with a named hero product link — 14 of 34 evaluated trends had a specific product anchor.
- **Client Archetype Coverage**: archetypes matched across shortlist — 摇滚缪斯 Yáogǔn Miùsī, 智识派 Zhishì Pài, 独立新贵 Dúlì Xīnguì
- **Trend Velocity**: scores computed from engagement_recency_pct (7-day recency window).
- **Cross-Run Persistence**: scores computed from run_count (deduplication merged trends retain count).

---

## Shortlist Summary

Shortlisted **4** trends (real: 4, synthetic: 0):

| # | Trend | Score | Archetype | Hero Product | Pillar | CA Utility | Velocity |
|---|-------|-------|-----------|-------------|--------|-----------|---------|
| 1 | **[run_0011_t01]** Celine Minimalism and Quiet Luxury | 8.24 | 独立新贵 Dúlì Xīnguì | Celine 70s high-waist wide-leg trousers | Architectural Restraint | 9 | 6.6 |
| 2 | **[run_0013_t01]** Celine's Quiet Luxury Trend | 8.14 | 智识派 Zhishì Pài | Triomphe canvas shoulder bag | Architectural Restraint | 9 | 6.6 |
| 3 | **[run_0012_t01]** Celine's Minimalist Aesthetic | 7.79 | 智识派 Zhishì Pài | Triomphe chain bag | Architectural Restraint | 8 | 6.6 |
| 4 | **[run_0010_t01]** Minimalist Tailoring & Structure | 7.66 | 智识派 Zhishì Pài | Celine Essential slim-cut tuxedo blazer | Architectural Restraint | 8 | 5.7 |

---

## Failure Cases (5 Lowest Scoring)

- **[run_0017_t07]** CELINE 26 Summer Men's Relaxed Jackets — score: 3.65
  - Reason: client_persona_match — lacks deep resonance with archetypes
  - Target archetype: no archetype matched | client_persona_match: 3 | ca_conversational_utility: 4 | novelty: 3
- **[run_0020_t04]** CELINE 26 Summer Menswear Styling Highlights — score: 4.05
  - Reason: ca_conversational_utility: lacks specific product link for effective conversation.
  - Target archetype: 摇滚缪斯 Yáogǔn Miùsī | client_persona_match: 6 | ca_conversational_utility: 1 | novelty: 5
- **[run_0018_t07]** Relaxed and Effortless Menswear Styling — score: 4.05
  - Reason: client_persona_match - this trend does not align significantly with Celine's archetypes focusing on luxury attitude.
  - Target archetype: no archetype matched | client_persona_match: 3 | ca_conversational_utility: 5 | novelty: 4
- **[run_0021_t04]** CELINE 26 Summer Menswear Soft Relaxed Jacket Showcase — score: 4.25
  - Reason: client_persona_match — does not align well with Celine's client archetypes that are specifically focused on women's fashion.
  - Target archetype: no archetype matched | client_persona_match: 3 | ca_conversational_utility: 4 | novelty: 5
- **[run_0021_t03]** Celine Bag Selection Tips Content — score: 4.25
  - Reason: client_persona_match - it does not align well with the high-design expectations of Celine's intended clientele.
  - Target archetype: no archetype matched | client_persona_match: 4 | ca_conversational_utility: 5 | novelty: 4

---

## Known Limitations

1. Runs 0001–0008 are beauty category and excluded — not relevant for Celine.
2. Runs 0009–0013 contain identical underlying XHS data (same 3 posts scraped across 5 runs).
3. Synthetic trends are clearly marked `data_type: synthetic` and should not be presented as real XHS signal.
4. No image URLs captured — scraping ran with `--no-detail` flag.
