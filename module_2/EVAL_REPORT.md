# Module 2 — Evaluation Report

**Run ID:** m2_20260412_072005  
**Generated at:** 2026-04-12T07:20:05.245692+00:00  
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
- Passed to LLM: **35**
- Shortlisted: **13**
- Noise reduction rate: **81.2%**

---

## Quality Checks

### 1. Off-Brand Rate
- Off-brand count: 0 (0.0% of input)
  - Taboo keyword rejections: 0
  - LLM brand_fit < 5: 0

### 2. Explanation Specificity (LLM confidence breakdown)
- High: 16 (45.7%)
- Medium: 19 (54.3%)
- Low: 0 (0.0%)

### 3. Noise Reduction
- 81.2% of input trends were filtered before reaching the shortlist.

### 4. New Dimensions (Week 11)
- **CA Conversational Utility**: % of shortlisted trends with a named hero product link — 13 of 35 evaluated trends had a specific product anchor.
- **Client Archetype Coverage**: archetypes matched across shortlist — null, 摇滚缪斯 Yáogǔn Miùsī, 智识派 Zhishì Pài, 独立新贵 Dúlì Xīnguì
- **Trend Velocity**: scores computed from engagement_recency_pct (7-day recency window).
- **Cross-Run Persistence**: scores computed from run_count (deduplication merged trends retain count).

---

## Shortlist Summary

Shortlisted **13** trends (real: 13, synthetic: 0):

| # | Trend | Score | Archetype | Hero Product | Pillar | CA Utility | Velocity |
|---|-------|-------|-----------|-------------|--------|-----------|---------|
| 1 | **[run_0013_t01]** Celine's Quiet Luxury Trend | 8.34 | 智识派 Zhishì Pài | Celine Triomphe canvas shoulder bag | null | 9 | 6.6 |
| 2 | **[run_0012_t01]** Celine's Minimalist Aesthetic | 7.89 | 智识派 Zhishì Pài | Celine Triomphe canvas shoulder bag | Architectural Restraint | 8 | 6.6 |
| 3 | **[run_0009_t01]** Mixed Beauty Trend Signals | 7.86 | 独立新贵 Dúlì Xīnguì | Celine Triomphe canvas shoulder bag | Architectural Restraint | 8 | 5.7 |
| 4 | **[run_0010_t01]** Minimalist Tailoring & Structure | 7.86 | 智识派 Zhishì Pài | Celine Essential slim-cut tuxedo blazer | Architectural Restraint | 9 | 5.7 |
| 5 | **[run_0019_t02]** Celine Blue Label Design Detail Appreciation | 7.80 | 智识派 Zhishì Pài | Celine Classique 16 bag | Architectural Restraint | 8 | 5.0 |
| 6 | **[run_0012_t02]** Celine Workplace Fashion | 7.70 | 独立新贵 Dúlì Xīnguì | Celine 16 bag | null | 7 | 10.0 |
| 7 | **[run_0021_t01]** Celine Blue Label Design Appreciation | 7.70 | 智识派 Zhishì Pài | — | — | 8 | 5.0 |
| 8 | **[run_0014_t01]** Mixed Trend Signals | 7.65 | 摇滚缪斯 Yáogǔn Miùsī | Celine oversized leather biker jacket | Youth Without Apology | 8 | 5.0 |
| 9 | **[run_0018_t02]** Quiet Luxury Minimalism | 7.65 | 智识派 Zhishì Pài | Celine Essential slim-cut tuxedo blazer | Architectural Restraint | 8 | 5.0 |
| 10 | **[run_0017_t02]** Celine Blue Label Minimalist Aesthetics | 7.60 | 独立新贵 Dúlì Xīnguì | — | Architectural Restraint | 8 | 5.0 |
| 11 | **[run_0023_t02]** Celebrity Outfit Decoding and Influence Content | 7.35 | 摇滚缪斯 Yáogǔn Miùsī | CELINE 16手袋 (Soft16 bag) | Youth Without Apology | 8 | 5.0 |
| 12 | **[run_0018_t06]** Celebrity-Influenced Brand Enthusiasm | 7.25 | 摇滚缪斯 Yáogǔn Miùsī | Celine 26 bag | Youth Without Apology | 8 | 5.0 |
| 13 | **[run_0019_t06]** Celebrity Celine Show Attendance and Styling Highlights | 7.00 | 摇滚缪斯 Yáogǔn Miùsī | Celine oversized leather biker jacket | Youth Without Apology | 7 | 5.0 |

---

## Failure Cases (5 Lowest Scoring)

- **[run_0011_t03]** Celine Tailoring Insights — score: 4.15
  - Reason: ca_conversational_utility - no direct product connection undermines immediate usefulness for conversations.
  - Target archetype: no archetype matched | client_persona_match: 3 | ca_conversational_utility: 4 | novelty: 4
- **[run_0021_t02]** CELINE Early Spring Handbag Showcase — score: 4.45
  - Reason: ca_conversational_utility below 5 — the trend is highly seasonal and might not align with current client interests.
  - Target archetype: null | client_persona_match: 5 | ca_conversational_utility: 4 | novelty: 4
- **[run_0021_t04]** CELINE 26 Summer Menswear Soft Relaxed Jacket Showcase — score: 4.55
  - Reason: ca_conversational_utility below 5 — the trend lacks clear product references.
  - Target archetype: null | client_persona_match: 4 | ca_conversational_utility: 3 | novelty: 5
- **[run_0012_t03]** Celine Tailoring and Fabric Insights — score: 4.85
  - Reason: ca_conversational_utility - no extracted product or strong actionable connection
  - Target archetype: no archetype matched | client_persona_match: 6 | ca_conversational_utility: 4 | novelty: 5
- **[run_0017_t07]** CELINE 26 Summer Men's Relaxed Jackets — score: 4.95
  - Reason: client_persona_match: trend does not connect with defined archetypes due to a lack of specificity in style and audience engagement.
  - Target archetype: no archetype matched | client_persona_match: 3 | ca_conversational_utility: 4 | novelty: 5

---

## Known Limitations

1. Runs 0001–0008 are beauty category and excluded — not relevant for Celine.
2. Runs 0009–0013 contain identical underlying XHS data (same 3 posts scraped across 5 runs).
3. Synthetic trends are clearly marked `data_type: synthetic` and should not be presented as real XHS signal.
4. No image URLs captured — scraping ran with `--no-detail` flag.
