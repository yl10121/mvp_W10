# Module 1 -- XHS Trend Object Builder: Test Plan

---

## D1 -- Who Will Test

### Reviewer Roles

| Role | Why they matter |
|------|-----------------|
| **Client Advisor (CA)** | Directly uses trend intelligence to advise clients on product selection; knows what language and labels resonate on the sales floor. |
| **CA Manager** | Evaluates whether trend signals are actionable at a team/store level; cares about accuracy and deduplication so managers do not brief contradictory trends. |
| **Trend / Social Media Analyst** | Judges whether the clustering logic produces meaningful, non-overlapping trend objects and whether the evidence (post IDs, snippets, engagement metrics) is sufficient to trust the signal. |

### Target

3-5 real reviewers over **Weeks 11-12**. Each reviewer completes one 10-minute session per run they evaluate.

### Proxy Plan (if real access is limited)

If recruiting working CAs or analysts is not feasible within the timeline, substitute with the closest available proxies:

| Proxy pool | Rationale |
|------------|-----------|
| Fashion marketing students (graduate or senior undergraduate) | Familiar with brand positioning, trend cycles, and social media analysis frameworks. |
| Luxury retail associates (current or recent) | Hands-on experience with how trend information is consumed in a store context. |
| XHS power users who follow luxury brands | Native platform literacy; can judge whether scraped posts and cluster labels feel authentic and complete. |

When using proxies, note the substitution in the feedback file so downstream analysis accounts for expertise level.

---

## D2 -- 10-Minute Test Script

Total time: ~10 minutes per reviewer.

### Step 1 -- Show one input example (30 seconds)

Open `data/xhs_posts.json` and display 2-3 raw post records to the reviewer. Point out the key fields they will see referenced later:

- `post_id`, `title`, `caption` (the content the system reads)
- `likes`, `comments`, `saves` (engagement metrics the system aggregates)
- `hashtags`, `brand`, `category` (metadata used for filtering and clustering)

Example record to highlight:

```
post_id: p004
title: "静奢风才是真正的有钱人穿搭｜Celine教科书"
likes: 18765 | comments: 1023 | saves: 5432
hashtags: #静奢风, #QuietLuxury, #Celine, #低调奢华, #老钱风
```

Tell the reviewer: "This is one of ~50 posts the system ingested. The module clusters posts like this into named trend objects."

### Step 2 -- Run the module (30-60 seconds)

Run `xhs_trend_builder.py` on the full batch in front of the reviewer (or show a pre-recorded terminal run if live execution is impractical):

```bash
.venv/bin/python3 xhs_trend_builder.py --live
```

The `--live` flag keeps spinner stages visible briefly so the reviewer can follow each pipeline step: load, retrieve, cluster, label, write.

Point out the terminal summary lines that print each trend:

```
- t01 | Celine's Quiet Luxury Trend | conf=high | source=llm | posts=5 | eng=73,459
- t02 | ...                          | conf=high | source=llm | posts=3 | eng=...
- t03 | ...                          | conf=high | source=llm | posts=2 | eng=...
```

### Step 3 -- Show output and evidence (2 minutes)

Open the generated file `outputs/runs/run_XXXX_trend_objects.json`. For each trend object, walk the reviewer through:

1. **Label** -- the short name the system assigned (e.g., "Celine's Quiet Luxury Trend").
2. **Summary** -- one-sentence description of what the trend represents.
3. **Evidence block**:
   - `post_ids` -- which specific posts support this trend.
   - `snippets` -- title-level text pulled from those posts.
   - `posts` -- full post records with likes/comments/saves so the reviewer can verify engagement.
4. **Metrics** -- `post_count`, `total_engagement`, `avg_engagement`, `top_keywords`.
5. **Confidence** and **ai_reasoning** -- why the system chose high/medium/low and how it justified grouping these posts.

Ask the reviewer to read the evidence block for at least one trend before answering questions.

### Step 4 -- Ask three questions (5 minutes)

Present each question verbally and give the reviewer time to think before answering.

**Question 1 -- Label clarity**
> "Is this trend label accurate for these posts? Does the label clearly describe what the clustered posts have in common?"

Listen for: whether the label is too vague, too specific, misleading, or uses jargon the reviewer would not use.

**Question 2 -- Evidence sufficiency**
> "Would you trust this trend signal based on the evidence shown? Are the post IDs, snippets, and metrics enough for you to act on this trend?"

Listen for: whether the reviewer wants more posts, different metrics, date ranges, or visual proof (images/video).

**Question 3 -- Deduplication quality**
> "Are any of these trend clusters duplicates or too similar? Should any two trends be merged, or does each feel distinct?"

Listen for: overlap between trend objects that the system failed to merge, or trends that feel like the same signal reworded.

### Step 5 -- Capture rating and comment (2 minutes)

Hand the reviewer the rating form (paper or digital). Collect:

| Field | Format |
|-------|--------|
| **Usefulness / quality** | 1-5 scale (1 = not useful, 5 = production-ready) |
| **Trust** | 1-5 scale (1 = would not act on this, 5 = would brief a client based on this) |
| **What is missing, wrong, or risky?** | Free text -- anything the reviewer noticed that was absent, incorrect, duplicated, or could cause a bad decision |

Record responses in `outputs/runs/run_XXXX_feedback.json` using the existing schema:

```json
{
  "reviewer": "Name / Role",
  "run_id": "run_XXXX",
  "usefulness_quality": 4,
  "trust": 3,
  "missing_wrong_risky": "Trend t01 and t03 feel overlapping. Would like to see date range per trend."
}
```

---

## D3 -- Book Sessions Now

Use the table below to track booked review sessions. Fill in as sessions are confirmed.

| # | Name / Role | Date / Time | Format |
|---|-------------|-------------|--------|
| 1 | TBD / CA | Week 11 -- TBD | In-person / Video |
| 2 | TBD / CA Manager | Week 11 -- TBD | In-person / Video |
| 3 | TBD / Trend Analyst | Week 12 -- TBD | Video |
| 4 | TBD / Proxy (fashion marketing student) | Week 12 -- TBD | Video |
| 5 | TBD / Proxy (XHS power user) | Week 12 -- TBD | Video |

**Booking checklist:**

- [ ] Send calendar invite with 15-minute block (10 min session + 5 min buffer).
- [ ] Attach or link to this test script so the reviewer knows what to expect.
- [ ] Confirm the reviewer has access to view JSON files or prepare a screen share.
- [ ] Pre-run `xhs_trend_builder.py` to have output files ready as backup.

---

## E -- 7-Line Demo Script

Below is a 7-line narrated demo script. Each line is one action or statement the presenter delivers. The script covers a batch run, Supabase read/write, the evaluation report, and one failure case with a planned fix.

```
LINE 1:  "Module 1 takes 50 raw Xiaohongshu posts for Celine -- scraped live from XHS -- and clusters them into evidence-backed trend objects in a single batch run."

LINE 2:  [Run the command]  .venv/bin/python3 xhs_trend_builder.py --live
         Show the terminal as it loads 50 posts, retrieves 38 in the time window, clusters them, calls the LLM for labels, and writes 3 trend objects to outputs/runs/.

LINE 3:  "Every run automatically syncs to Supabase: posts go to module1_xhs_posts, trend objects go to module1_trend_objects, and the run log goes to module1_run_logs -- so downstream modules can read trends directly from the database without touching local files."

LINE 4:  [Open outputs/runs/run_XXXX_trend_objects.json]
         Walk through one trend object: show the label, the 5 supporting post_ids, the title snippets, total_engagement of 73,459, confidence=high, and the ai_reasoning paragraph that explains why these posts belong together.

LINE 5:  [Open outputs/runs/run_XXXX_feedback.json]
         "Three reviewers scored this run. Average usefulness was 4.3 out of 5. One reviewer flagged that trend t01 and t03 may overlap -- that is the kind of signal we use to improve the clustering prompt."

LINE 6:  "One known failure: when post volume is low -- fewer than 10 posts in the time window -- the system still forces clusters and produces trends with only 2 posts each, which reviewers rated as low-trust. The planned fix is a minimum-evidence gate: if a cluster has fewer than 3 posts or total engagement below 5,000, the system will flag it as 'weak signal' rather than presenting it as a confirmed trend."

LINE 7:  "Next step: approved trend objects feed into Module 2 for materiality ranking, where they get scored against the brand profile and prioritized for the client brief."
```
