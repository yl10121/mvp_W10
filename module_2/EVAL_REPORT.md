# Module 2 — Evaluation Report

**Run ID:** m2_20260330_041951  
**Generated at:** 2026-03-30T04:19:51.149275+00:00  
**Brand:** Celine

---

## Batch Composition

| Source | Count |
|--------|-------|
| Real XHS (luxury_fashion) | 69 |
| Synthetic (luxury_fashion) | 25 |
| Beauty runs skipped | 40 |
| **Total input to filter** | **94** |

---

## Filter Results

- Pre-filter rejected: **55**
- Passed to LLM: **39**
- Shortlisted: **15**
- Noise reduction rate: **84.0%**

---

## Quality Checks

### 1. Off-Brand Rate
- Off-brand count: 1 (1.1% of input)
  - Taboo keyword rejections: 1
  - LLM brand_fit < 5: 0

### 2. Explanation Specificity (LLM confidence breakdown)
- High: 21 (53.8%)
- Medium: 18 (46.2%)
- Low: 0 (0.0%)

### 3. Noise Reduction
- 84.0% of input trends were filtered before reaching the shortlist.

---

## Shortlist Summary

Shortlisted **15** trends (real: 4, synthetic: 11):

- **[synthetic_t03]** Triomphe Hardware Investment — score: 9.50
- **[synthetic_t06]** French Intellectual Editorial Aesthetic — score: 9.20
- **[synthetic_t02]** Architectural Silhouette Dressing — score: 9.10
- **[synthetic_t10]** Oversized Structured Blazer Power Dressing — score: 9.10
- **[synthetic_t04]** Monochromatic Precision Dressing — score: 9.00
- **[synthetic_t24]** Clean Minimalist Aesthetic as Identity — score: 8.75
- **[synthetic_t18]** Day-to-Night Minimalist Dressing — score: 8.55
- **[synthetic_t23]** Satin and Silk Luxury Surface Dressing — score: 8.55
- **[run_0012_t01]** Celine's Minimalist Aesthetic — score: 8.50
- **[synthetic_t15]** Understated Leather Goods Connoisseurship — score: 8.35
- **[run_0013_t01]** Celine's Quiet Luxury Trend — score: 8.30
- **[synthetic_t14]** Capsule Wardrobe Investment Mentality — score: 8.25
- **[synthetic_t17]** High-Waist Wide Leg Trouser Mastery — score: 8.25
- **[run_0009_t01]** Mixed Beauty Trend Signals — score: 8.20
- **[run_0010_t01]** Minimalist Tailoring & Structure — score: 8.20

---

## Failure Cases (5 Lowest Scoring)

- **[run_0009_t03]** Mixed Beauty Trend Signals — score: 5.20
  - Reason: category_fit — insufficient relevance for Celine's luxury positioning
- **[run_0011_t03]** Celine Tailoring Insights — score: 5.45
  - Reason: materiality - total_engagement is not strong enough
- **[run_0010_t02]** Luxury Handbag & Leather Goods — score: 5.75
  - Reason: materiality — insufficient engagement across posts
- **[run_0013_t03]** Celine Tailoring Insights — score: 5.80
  - Reason: freshness: insufficient recent activity in posts
- **[synthetic_t09]** Neutral Palette Color Theory — score: 5.80
  - Reason: materiality — lacks strong enough engagement and direct product relevance

---

## Known Limitations

1. Runs 0001–0008 are beauty category and excluded — not relevant for Celine.
2. Runs 0009–0013 contain identical underlying XHS data (same 3 posts scraped across 5 runs).
3. Synthetic trends are clearly marked `data_type: synthetic` and should not be presented as real XHS signal.
4. No image URLs captured — scraping ran with `--no-detail` flag.
