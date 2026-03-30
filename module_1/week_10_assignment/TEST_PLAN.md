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

Tell the reviewer: "This is one of 197 posts the system ingested. The module clusters posts like this into named trend objects."

### Step 2 -- Run the module (30-60 seconds)

Run `xhs_trend_builder.py` on the full batch in front of the reviewer (or show a pre-recorded terminal run if live execution is impractical):

```bash
.venv/bin/python3 xhs_trend_builder.py && .venv/bin/python3 eval_harness.py
```

The terminal shows each pipeline step: load 197 posts, cluster via LLM-first logic, label, write 8 trend objects to outputs/runs/, then run the eval harness.

Point out the terminal summary lines that print each trend:

```
- t01 | Old Celine vs New Celine Nostalgia Debate            | conf=high | source=llm
- t02 | Celine Box Bag Relevance and Popularity Debate        | conf=high | source=llm
- t03 | Soft 16 Bag Functional Reviews and Styling            | conf=high | source=llm
- t04 | Celine 26 Spring/Summer Fashion Show Content          | conf=high | source=llm
- t05 | Celebrity Outfit Decoding and Influence               | conf=high | source=llm
- t06 | Celine Bag Unboxing and Purchase Experience           | conf=high | source=llm
- t07 | Celine Men's Fashion and Male Accessory Focus         | conf=high | source=llm
- t08 | French Old Money and Elegant Aesthetic Styling        | conf=high | source=llm
```

### Step 3 -- Show output and evidence (2 minutes)

Open the generated file `outputs/runs/run_0022_trend_objects.json`. For each trend object, walk the reviewer through:

1. **Label** -- the short name the system assigned (e.g., "Old Celine vs New Celine Nostalgia Debate").
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

Record responses in `outputs/runs/run_0022_feedback.json` using the existing schema:

```json
{
  "reviewer": "Name / Role",
  "run_id": "run_0022",
  "usefulness_quality": 4,
  "trust": 3,
  "missing_wrong_risky": "Trend t01 and t03 feel overlapping. Would like to see date range per trend."
}
```

---

## D3 -- Book Sessions Now

Use the table below to track booked review sessions. Fill in as sessions are confirmed.

| # | Name / Role | Location | Date / Time | Format |
|---|-------------|----------|-------------|--------|
| 1 | CA / Valentino | Qiantan Taikoo Li, Shanghai | Week 10 (this week) | In-person |
| 2 | CA / Armani | Xujiahui Grand Gateway, Shanghai | Week 11 | In-person |
| 3 | CA / Stuart Weitzman | Xujiahui Grand Gateway, Shanghai | Week 11 | In-person |
| 4 | TBD / Proxy (fashion marketing student) | -- | Week 12 -- TBD | Video |
| 5 | TBD / Proxy (XHS power user) | -- | Week 12 -- TBD | Video |

**Booking checklist:**

- [ ] Send calendar invite with 15-minute block (10 min session + 5 min buffer).
- [ ] Attach or link to this test script so the reviewer knows what to expect.
- [ ] Confirm the reviewer has access to view JSON files or prepare a screen share.
- [ ] Pre-run `xhs_trend_builder.py` to have output files ready as backup.

---

## E -- 7-Line Demo Script

Below is a 7-line narrated demo script. Each line is one action or statement the presenter delivers. The script covers a batch run of real XHS posts, LLM-first clustering, Supabase sync, the eval harness results, and one failure case with a planned fix.

Real trend labels from run_0022:

1. Old Celine vs New Celine Nostalgia Debate
2. Celine Box Bag Relevance and Popularity Debate
3. Soft 16 Bag Functional Reviews and Styling
4. Celine 26 Spring/Summer Fashion Show Content
5. Celebrity Outfit Decoding and Influence
6. Celine Bag Unboxing and Purchase Experience
7. Celine Men's Fashion and Male Accessory Focus
8. French Old Money and Elegant Aesthetic Styling

```
LINE 1:  "Module 1 takes 197 raw Xiaohongshu posts -- scraped live from XHS -- and clusters them into evidence-backed trend objects using LLM-first clustering in a single batch run."

LINE 2:  [Run the command]  .venv/bin/python3 xhs_trend_builder.py && .venv/bin/python3 eval_harness.py
         Show the terminal as it loads 197 posts, clusters them via LLM-first logic, and writes 8 XHS content trends to outputs/runs/. Then the eval harness runs automatically and prints its report.

LINE 3:  "Every run automatically syncs to Supabase: 60 posts go to module1_xhs_posts, 8 trend objects go to module1_trend_objects, and the run log goes to module1_run_logs -- so downstream modules can read trends directly from the database without touching local files."

LINE 4:  [Open outputs/runs/run_0022_trend_objects.json]
         Walk through the 8 trend labels produced by LLM-first clustering. Show one trend object in detail: the label, the supporting post_ids, the title snippets, engagement metrics, confidence, and the ai_reasoning paragraph that explains why these posts belong together.

LINE 5:  [Show eval harness output]
         "The eval harness checks three things automatically. Evidence sufficiency: passed -- every trend has enough supporting posts. Duplication rate: the harness found 5 shared post_ids across clusters, meaning some posts appear in more than one trend. Label clarity: 1 label exceeded 8 words, which flags it for possible shortening."

LINE 6:  "One known failure from eval: 5 post_ids are shared across clusters, which means some evidence overlaps between trends. The planned fix is to add a deduplication pass that removes shared post_ids before writing trend objects, so each post supports exactly one trend."

LINE 7:  "Next step: approved trend objects feed into Module 2 for materiality ranking, where they get scored against the brand profile and prioritized for the client brief."
```
