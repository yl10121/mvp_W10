# Module 1 -- Week 11 Improvement Spec

Based on in-class feedback (Week 10 demo, 2026-03-30).

---

## 1. Competitor Scraping

**Current:** Only scrapes Celine keywords.
**Change:** Scrape competitor brands in the same run to compare trend signals across LVMH and rival maisons.

### Brands to add

| Brand | Keywords to scrape |
|-------|-------------------|
| Celine | Celine, Celine穿搭, Celine包包, 赛琳 (already done) |
| Dior | Dior穿搭, Dior包包, Dior秀场, 迪奥 |
| Louis Vuitton | LV穿搭, LV包包, 路易威登, Louis Vuitton |
| Loewe | Loewe穿搭, Loewe包包, 罗意威 |
| Chanel | Chanel穿搭, Chanel包包, 香奈儿 |
| Bottega Veneta | BV穿搭, BV包包, 葆蝶家 |

### Implementation
- Add `--brands` flag to `run_celine_scrape.py` (rename to `run_luxury_scrape.py`)
- Each post gets a `brand` field based on which keyword group matched
- Trend objects tagged with which brands they relate to
- Enables cross-brand trend comparison: "quiet luxury is trending for Celine AND Loewe but not LV"

---

## 2. 30-Day Rolling Time Window

**Current:** No time window filter (scrapes whatever XHS returns, dates are inconsistent).
**Change:** Filter to posts from the last 30 days from scrape date.

### Implementation
- Normalize all XHS date formats to ISO (handle "03-21", "03-21 陕西", "2025-10-05", relative dates)
- Set `time_window.start_date` = scrape_date - 30 days
- Set `time_window.end_date` = scrape_date
- Drop posts outside the window before clustering
- This ensures trend objects only reflect what is happening NOW, not historical noise

---

## 3. Emerging vs Established Trend Classification

**Current:** All trends are equal -- no distinction between a trend that just started spiking and one that has been steady for weeks.
**Change:** Classify each trend as EMERGING, ESTABLISHED, or FADING based on post frequency and recency patterns.

### Definitions

| Classification | Signal |
|---------------|--------|
| **EMERGING** | Most posts are from the last 7 days. Post frequency is accelerating (more posts in recent days than earlier days). Low total volume but high velocity. |
| **ESTABLISHED** | Posts spread across the full 30-day window. Steady frequency. High total volume and engagement. |
| **FADING** | Most posts are from 15-30 days ago. Post frequency is decelerating. Engagement per post is dropping. |

### New fields on trend objects
```json
{
  "trend_classification": "emerging",
  "velocity": {
    "posts_last_7d": 8,
    "posts_8_to_14d": 3,
    "posts_15_to_30d": 1,
    "acceleration": "increasing"
  }
}
```

---

## 4. Post Frequency and Recency Metrics

**Current:** Only tracks `post_count` and `total_engagement` (raw totals).
**Change:** Add time-based frequency metrics that show HOW the trend is moving, not just how big it is.

### New metrics per trend

| Metric | What it measures | Formula |
|--------|-----------------|---------|
| `post_frequency_per_week` | Average posts per week in the 30-day window | post_count / (days_spanned / 7) |
| `avg_days_between_posts` | Average gap between consecutive posts | mean(date[i+1] - date[i]) for all posts sorted by date |
| `recency_score` | How recent the latest activity is | 1.0 if last post is today, decays linearly to 0.0 at 30 days |
| `frequency_acceleration` | Is posting speeding up or slowing down? | (posts_last_7d / 7) / (posts_8_to_30d / 23) -- ratio > 1.0 means accelerating |
| `engagement_recency` | Are recent posts getting more or less engagement? | avg_engagement_last_7d / avg_engagement_8_to_30d |

### Example output
```json
{
  "metrics": {
    "post_count": 12,
    "total_engagement": 48345,
    "post_frequency_per_week": 2.8,
    "avg_days_between_posts": 2.5,
    "recency_score": 0.85,
    "frequency_acceleration": 1.6,
    "engagement_recency": 1.3
  }
}
```

---

## 5. Revised Engagement Weighting

**Current:** `total_engagement = likes + comments + saves` (all weighted equally).
**Change:** Weight comments and likes higher because they indicate stronger user intent.

### New weights

| Signal | Current weight | New weight | Rationale |
|--------|---------------|------------|-----------|
| Likes | 1x | 1.5x | Low effort but high signal -- users actively endorse the content |
| Comments | 1x | 3x | Highest effort -- users are participating in discourse, not just scrolling past |
| Saves | 1x | 1x | Indicates utility/reference value but less about trending discourse |

### Formula
```
weighted_engagement = (likes * 1.5) + (comments * 3) + (saves * 1)
```

### Why comments matter more
- A post with 100 likes and 50 comments has more trend signal than a post with 500 likes and 2 comments
- Comments = discourse = people are TALKING about the trend, not just double-tapping
- Comments often contain opposing views which indicate a DEBATE (stronger trend signal)

---

## 6. Comment and Like Frequency Metrics

**Current:** Only stores total comment count and total likes per post.
**Change:** Track engagement velocity -- how quickly comments and likes are accumulating.

### New metrics per trend

| Metric | What it measures |
|--------|-----------------|
| `avg_comments_per_post` | Average comment count across posts in this trend |
| `avg_likes_per_post` | Average likes across posts in this trend |
| `comment_density` | comments / post_count -- higher = more discourse |
| `engagement_per_day` | total_weighted_engagement / days_spanned |
| `high_comment_post_ratio` | % of posts with comments > 50 (indicates discussion posts vs. passive content) |

### Example
```json
{
  "engagement_detail": {
    "avg_comments_per_post": 42,
    "avg_likes_per_post": 1200,
    "comment_density": 42.0,
    "engagement_per_day": 1612,
    "high_comment_post_ratio": 0.58
  }
}
```

---

## 7. Updated Trend Scoring Formula

Combining all the above into a single trend ranking score:

```
trend_score = (
    weighted_engagement * 0.25
  + recency_score * 0.20
  + frequency_acceleration * 0.20
  + comment_density * 0.15
  + post_frequency_per_week * 0.10
  + high_comment_post_ratio * 0.10
)
```

This rewards trends that are:
- High engagement (especially comments)
- Recent (last 7 days)
- Accelerating (posting frequency increasing)
- Generating discourse (high comment density)
- Consistent (regular post frequency)

---

## 8. Better Scraping Keywords (Trend-Descriptive, Not Brand Names)

*Feedback note (Mon, 30 Mar 26): "write better trend queries and then do not include the brand name, only descriptors for a more general trend."*

**Current:** Keywords are brand-centric -- "Celine包包", "Celine穿搭", "Celine Triomphe". This limits results to posts that explicitly mention Celine and misses broader trend signals.

**Change:** Add trend-descriptive keywords that capture the AESTHETIC or BEHAVIOR, not the brand. This surfaces posts where users are participating in a trend without necessarily tagging a brand.

### Current keywords (brand-centric)
```
Celine, Celine穿搭, Celine包包, Celine Triomphe, Celine Box, ...
```

### New keywords to add (trend-descriptive, no brand name)

| Trend signal | Keywords |
|-------------|----------|
| Quiet luxury / old money | 静奢风, 老钱风穿搭, quiet luxury, 低调奢华, 安静的奢侈 |
| Minimalist styling | 极简穿搭, 高级感穿搭, 少即是多, 胶囊衣橱, 断舍离穿搭 |
| Investment pieces | 值得入的包, 经典款不过时, 保值包包, 一包传三代 |
| Bag nostalgia / relevance | 时代的眼泪, 还值得买吗, 过时了吗, 经典还是过时 |
| Commute / work luxury | 通勤包推荐, 上班穿搭高级, 职场穿搭, 通勤神器 |
| French / Parisian style | 法式穿搭, 巴黎风, 法式优雅, 法式慵懒 |
| Secondhand / resale | 二手奢侈品, 中古包, 回收行情, 二手值多少 |
| Celebrity styling | 明星同款, 机场穿搭, 秀场街拍, 同款穿搭 |

### Why this matters
- Brand-only keywords create an echo chamber -- you only find posts that already mention Celine
- Trend-descriptive keywords find the BROADER SIGNAL: "quiet luxury" posts might reference Celine, Loewe, The Row, or no brand at all
- This lets Module 2 assess whether Celine is riding a wave or missing one
- A trend like "commute bag reviews" that mentions competitors but not Celine is valuable intelligence

### Implementation
- Split keyword list into two groups: `brand_keywords` and `trend_keywords`
- Tag each post with `keyword_type: "brand"` or `keyword_type: "trend"`
- Trend objects report what % of their posts came from brand vs trend keywords
- If a trend is >80% from trend keywords with zero brand mentions, flag as "competitor signal"

---

## 9. Brand-Agnostic Trend Labels

*Feedback note (Mon, 30 Mar 26): "do not include the brand name, only descriptors for a more general trend."*

**Current:** Trend labels include the brand name -- "Old Celine vs New Celine Nostalgia Debate", "Celine Box Bag Relevance Discourse".

**Change:** Trend labels should describe the TREND, not the brand. The brand association is metadata, not the label.

### Examples

| Current (brand in label) | New (brand-agnostic) | Brand tags |
|--------------------------|---------------------|------------|
| Old Celine vs New Celine Nostalgia Debate | Heritage vs Modern Creative Director Debate | Celine |
| Celine Box Bag Relevance Discourse | Classic Bag Relevance and Resale Value Discourse | Celine, Chanel, Dior |
| Soft 16 as Ultimate Commute Bag | Luxury Commute Bag Functional Reviews | Celine, Loewe, Fendi |
| Celebrity Outfit Decoding and Influence | Celebrity Show Attendance Outfit Analysis | Celine, Dior, LV |

### New field on trend objects
```json
{
  "label": "Heritage vs Modern Creative Director Debate",
  "brands_mentioned": ["Celine", "Dior"],
  "primary_brand": "Celine",
  "brand_mention_ratio": 0.85
}
```

### LLM prompt update
Add to the clustering prompt: "Trend labels must NOT contain brand names. Describe the trend behavior or aesthetic. Store brand names separately in a brands_mentioned array."

---

## Implementation Priority

| Priority | Change | Effort |
|----------|--------|--------|
| 1 | Brand-agnostic trend labels (no brand in label) | Small -- update LLM prompt + add brands_mentioned field |
| 2 | Trend-descriptive keywords (not just brand keywords) | Medium -- add ~30 new keywords, tag keyword_type |
| 3 | Revised engagement weighting (comments 3x, likes 1.5x) | Small -- change one formula |
| 4 | Post frequency + recency metrics | Medium -- add date parsing + new metric calculations |
| 5 | Emerging/Established/Fading classification | Medium -- add velocity logic + new field |
| 6 | 30-day rolling time window | Medium -- fix date normalization |
| 7 | Comment/like frequency metrics | Small -- aggregate existing data |
| 8 | Competitor scraping | Large -- new keywords, brand tagging, cross-brand comparison |

---

## Known Challenges and Solutions (from class feedback)

### Trend Detection Challenges

- Current system only searches brand names in titles
- Missing trends where celebrities wear products without mentioning brand
  - Example: Celebrity wearing Celine sunglasses/bag but post doesn't mention "Celine"
  - Brand still gets exposure but system can't detect it
- Need better trend queries that don't include brand name only -- use descriptors for more general trend detection

### Technical Implementation Issues

- Built custom AI solution using web browser automation (Playwright)
  - Logs into accounts and performs searches
  - Finds posts through automated browsing
- Cannot use official APIs due to platform restrictions
  - XHS/TikTok/social platforms forbid automated account access
  - Need to find alternative data sources or work within scraping constraints
- Personal account bias affecting results
  - XHS algorithm learns from personal search history
  - Getting irrelevant results (e.g. nail content instead of general fashion)
  - Solution: use fresh accounts or rotate accounts per keyword category

### Data Quality Problems

- Low post count currently (197 posts from 10 keywords before rate limiting)
- Need deduplication for similar titles (eval harness found 5 shared post_ids across clusters)
- Require concrete evaluation metrics (3 checks implemented: duplication, evidence sufficiency, label clarity)
- Brand profiles created in Module 3 as temporary solution
  - Difficulty making changes to existing personas
  - Training/Granville class integration challenges

### Keyword Strategy Solutions

- Develop descriptive keywords for each brand
  - Example: Celine = "French minimalist", "quiet luxury", "intellectual fashion" + other descriptors
  - Search broader terms rather than exact brand names
- Address competitor mentions
  - Track when celebrities use competing brands
  - Still relevant for brand monitoring even if it's not our target brand
- Create multiple accounts strategy
  - Companies use 50-100 accounts for different topics
  - Rotate accounts to avoid personal bias and algorithm contamination
  - Use dedicated accounts per keyword category to get clean results

---

Chat with meeting transcript: [https://notes.granola.ai/t/eccc39d5-3eff-4b13-a663-cd077f61d1c0](https://notes.granola.ai/t/eccc39d5-3eff-4b13-a663-cd077f61d1c0)

---

## Acceptance Criteria

- [ ] Trend objects include `trend_classification` (emerging/established/fading)
- [ ] Trend objects include `velocity` block with posts_last_7d, acceleration
- [ ] Engagement uses weighted formula (comments 3x, likes 1.5x, saves 1x)
- [ ] Each trend has `post_frequency_per_week`, `avg_days_between_posts`, `recency_score`
- [ ] Each trend has `comment_density`, `high_comment_post_ratio`
- [ ] At least 2 competitor brands scraped alongside Celine
- [ ] Trend labels contain NO brand names (brand stored in `brands_mentioned` array)
- [ ] Keyword list includes trend-descriptive keywords (静奢风, 通勤包推荐, etc.) alongside brand keywords
- [ ] Each post tagged with `keyword_type: "brand"` or `keyword_type: "trend"`
- [ ] All posts filtered to 30-day window from scrape date
- [ ] Eval harness updated with checks for new metrics
- [ ] Supabase schema updated for new fields
