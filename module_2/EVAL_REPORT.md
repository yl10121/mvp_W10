# Module 2 — Evaluation Report

**Run ID:** m2_20260329_152623  
**Generated at:** 2026-03-29T15:26:23.983657+00:00  
**Brand:** Celine

---

## Batch Composition

| Source | Count |
|--------|-------|
| Real XHS (luxury_fashion) | 15 |
| Synthetic (luxury_fashion) | 25 |
| Beauty runs skipped | 40 |
| **Total input to filter** | **40** |

---

## Filter Results

- Pre-filter rejected: **1**
- Passed to LLM: **39**
- Shortlisted: **15**
- Noise reduction rate: **62.5%**

---

## Quality Checks

### 1. Off-Brand Rate
- Off-brand count: 1 (2.5% of input)
  - Taboo keyword rejections: 1
  - LLM brand_fit < 5: 0

### 2. Explanation Specificity (LLM confidence breakdown)
- High: 22 (56.4%)
- Medium: 17 (43.6%)
- Low: 0 (0.0%)

### 3. Noise Reduction
- 62.5% of input trends were filtered before reaching the shortlist.

---

## Shortlist Summary

Shortlisted **15** trends (real: 4, synthetic: 11):

- **[synthetic_t03]** Triomphe Hardware Investment — score: 9.30
- **[run_0009_t01]** Mixed Beauty Trend Signals — score: 9.25
- **[run_0010_t01]** Minimalist Tailoring & Structure — score: 9.25
- **[synthetic_t22]** Season-less Wardrobe Building — score: 9.20
- **[synthetic_t02]** Architectural Silhouette Dressing — score: 9.10
- **[synthetic_t21]** Parisian Academic Intellectual Style — score: 9.10
- **[run_0013_t01]** Celine's Quiet Luxury Trend — score: 9.00
- **[synthetic_t23]** Satin and Silk Luxury Surface Dressing — score: 9.00
- **[synthetic_t24]** Clean Minimalist Aesthetic as Identity — score: 9.00
- **[synthetic_t06]** French Intellectual Editorial Aesthetic — score: 8.70
- **[synthetic_t10]** Oversized Structured Blazer Power Dressing — score: 8.70
- **[synthetic_t15]** Understated Leather Goods Connoisseurship — score: 8.65
- **[run_0011_t01]** Celine Minimalism and Quiet Luxury — score: 8.60
- **[synthetic_t08]** Cashmere Quiet Luxury Layering — score: 8.60
- **[synthetic_t14]** Capsule Wardrobe Investment Mentality — score: 8.55

---

## Failure Cases (5 Lowest Scoring)

- **[run_0012_t01]** Celine's Minimalist Aesthetic — score: 4.55
  - Reason: freshness and materiality – insufficient recent traction
- **[run_0010_t03]** Minimalist Tailoring & Structure — score: 5.10
  - Reason: freshness and materiality – not enough traction and low engagement
- **[run_0010_t02]** Luxury Handbag & Leather Goods — score: 5.25
  - Reason: materiality: insufficient engagement and interest with only 3 posts
- **[run_0009_t03]** Mixed Beauty Trend Signals — score: 5.40
  - Reason: materiality: insufficient engagement and post count
- **[run_0012_t02]** Celine Workplace Fashion — score: 5.55
  - Reason: freshness - low engagement and limited recency of posts

---

## Known Limitations

Top 5 Failure Cases:
All 5 failures share the same root cause: thin evidence clusters. Even though Module 1 scraped 50 real XHS posts per run with an average engagement of 160,636, those 50 posts got clustered into only 3 trend objects per run. This means some trend objects ended up with only 2–3 posts of evidence behind them — not because the data wasn't there, but because Module 1's clustering grouped most posts into the strongest trend and left the weaker trends with very little support.
Failure 1 — "Celine's Minimalist Aesthetic" (score 4.55) The label is perfectly on-brand for Celine but the evidence behind it was too thin — only a small cluster of posts with low recent activity. The AI correctly identified that 50 posts were scraped but only a handful actually pointed to this specific trend. The problem is that "minimalist aesthetic" is so broad it could describe almost everything Celine does — Module 1 couldn't find a tight enough cluster of posts specifically about this angle, so it ended up as a weak leftover trend from the clustering process.
Failure 2 — "Minimalist Tailoring & Structure" (score 5.10) This is a legitimate Celine trend but it overlapped heavily with other stronger trends in the same batch. When two trends are too similar, the AI splits the evidence between them and both end up weaker than if they had been merged into one stronger trend object. This is a duplication problem — Module 2 currently has no deduplication step before LLM evaluation.
Failure 3 — "Luxury Handbag & Leather Goods" (score 5.25) This one only had 3 posts of evidence despite 50 posts being available. This means Module 1 assigned most of the leather goods posts to a stronger trend object and this one got the leftovers. The AI saw only 3 posts and correctly said that's not enough to call it a confirmed trend — it could just be 3 random posts.
Failure 4 — "Mixed Beauty Trend Signals" (score 5.40) The name itself reveals the problem — Module 1 couldn't figure out what this cluster was about so it labelled it "mixed signals." This is a noise trend — posts that didn't fit cleanly anywhere else got grouped together. Module 2 passed it through because it was luxury_fashion category but the AI immediately recognised it had no coherent identity and rejected it.
Failure 5 — "Celine Workplace Fashion" (score 5.55) This had low engagement AND limited recency. Even though the overall batch had high engagement (160k average), this specific cluster had older posts with lower individual engagement. The AI treats recency and engagement as signals of whether a trend is actively resonating right now — older low-engagement posts suggest the trend may be fading.
Fix for next week:
1. Add deduplication before LLM evaluation Failures 1 and 2 are almost identical trends ("Minimalist Aesthetic" and "Minimalist Tailoring") that should have been merged into one stronger trend before being sent to the AI. Module 2 should compare trend labels and summaries before LLM evaluation and merge any trends that are more than 70% similar. This would give the merged trend more evidence and a higher score instead of two weak duplicates that both fail.
2. Add a minimum evidence quality check, not just post count Currently Module 2 checks post_count but not the quality of what those posts actually say. A trend with 3 highly specific Celine-relevant posts is more valuable than a trend with 5 vague generic posts. Module 2 should check whether the evidence snippets actually mention the brand or specific product categories, not just count how many posts there are.

