# Module 5 — In-Class Demo Script (Week 10, 5 minutes)

> **Part E: 7-line demo script — shows batch run, Supabase I/O, evaluation report, failure case + fix**

| # | Line | Action | What to show |
|---|------|--------|-------------|
| 1 | **Load inputs from Supabase** | `M5_SOURCE=supabase python3 module_5/agent.py --demo` | 20 clients loaded from `module4_client_memories` + 10 trends from `module2_trend_shortlist` |
| 2 | **Batch run** | `M5_SOURCE=supabase python3 module_5/agent.py --all` | 20 clients × 1 LLM call each; terminal prints angle + draft per client |
| 3 | **Supabase write** | *(auto after run)* | `module5_outreach_suggestions`: 20 new rows with `trend_signals_used` + `client_memory_ref` |
| 4 | **Evaluation report** | `python3 module_5/eval_agent.py` | Runs Quality Auditor on all 20 outputs → prints avg scores |
| 5 | **Show scores** | Open `EVAL_REPORT.md` | Groundedness 5.0, Over-Promotion 4.9, Would You Send 4.65 |
| 6 | **Failure case** | Point to BENCH_012 高以翔 (Would You Send = 4) | Draft cites UPF specs ("280g以下") — too technical for casual WeChat |
| 7 | **Planned fix** | Show `EVAL_REPORT.md → Fix section` | Add ≤80 char cap + anti-spec rule to `system-prompt v3` next week |

---

# Module 5 — Outreach Angle Agent: Full Demo Script (detailed)

> **Decision**: Given one client memory object + trend shortlist, suggest the best outreach angles and automatically draft WeChat messages referencing the relevant context.

---

## Step 0 — State the Decision



Our module tackles one core decision:

**"For a specific luxury client, what is the single best outreach angle right now — and what should the WeChat message say?"**

The agent takes two JSON inputs — **Client Memory** (purchase history, style profile, behavioral signals, contact rules) and a **Trend Shortlist** (5 current social/fashion trends with heat scores) — then outputs a personalized outreach strategy with drafted messages, evidence citations, confidence scores, and risk flags.

This is not a generic message generator. It replicates the decision-making process of a top-performing Client Advisor at an LVMH Maison: understanding the client, assessing timing, matching trends, choosing the right approach, and managing risk.

---

## Step 1 — Show the Prompt

=

### 1.1 User Input — How the CA Triggers the Agent

This agent has no interactive UI. The CA's intent is captured through a structured trigger flow: they select a client, and the system automatically assembles the user input from two data sources and fires it to the LLM.

```
CA Workflow
───────────────────────────────────────────────────────────────
  CA wants to          Agent reads           User Input
  reach out to   ───►  two sources    ───►   assembled &
  a client             automatically         sent to LLM
───────────────────────────────────────────────────────────────
       │                    │                      │
       ▼                    ▼                      ▼
  Selects client     client_memory.json      ## Client Memory
  (by client_id)  +  trend_shortlist.json    {client JSON}
  or runs --all                              ## Trend Shortlist
                                             {trends JSON}
```

The actual user input sent to the LLM for each client looks like this:

```
请为以下客户生成本周 outreach 建议。

## Client Memory
{
  "client_id": "C_102",
  "name": "陈雅琳",
  "vip_tier": "VVIP",
  "style_profile": ["architectural", "avant_garde"],
  "behavior_signals_90d": [ ... ],
  "sensitivity_flags": [ ... ],
  ...
}

## Trend Shortlist
{
  "trends": [
    { "trend_id": "T01", "name": "新中式 × 马术风", "stage": "peak", ... },
    { "trend_id": "T05", "name": "慢美学 / 匠心底蕴", "stage": "rising", ... },
    ...
  ]
}
```

The input contains **no instruction** — the full decision logic lives in the system prompt. The user input is purely data.

---

### 1.2 System Prompt — Structure Overview

```
┌─────────────────────────────────────────────────────────┐
│                     SYSTEM PROMPT                       │
├──────────────────────┬──────────────────────────────────┤
│  ROLE                │  Outreach Strategy Copilot       │
│                      │  for CAs at an LVMH Maison       │
├──────────────────────┼──────────────────────────────────┤
│  MAIN TASK           │  Inputs: Client Memory +         │
│                      │  Trend Shortlist                 │
│                      │  Outputs: angle / 2 drafts /     │
│                      │  evidence / confidence / risks   │
├──────────────────────┼──────────────────────────────────┤
│  THINKING FRAMEWORK  │  Layer 1: Client Understanding   │
│  (5 layers)          │  Layer 2: Moment Assessment      │
│                      │  Layer 3: Trend Relevance        │
│                      │  Layer 4: Angle Construction     │
│                      │    └─ 7-type outreach spectrum   │
│                      │  Layer 5: Risk Check             │
├──────────────────────┼──────────────────────────────────┤
│  RULES               │  Evidence: no hallucination      │
│                      │  Products: ≥2 signals required   │
│                      │  Guardrails: no FOMO / no fake   │
│                      │  intimacy / "delay" is valid     │
├──────────────────────┼──────────────────────────────────┤
│  VOICE & TONE        │  60–120 chars · WeChat-native    │
│                      │  personal / understated / warm   │
│                      │  Banned: urgency / discount /    │
│                      │  mass-message language           │
├──────────────────────┼──────────────────────────────────┤
│  OUTPUT FORMAT       │  Structured JSON schema          │
│  + FEW-SHOTS         │  3 examples: high / medium / low │
│                      │  confidence (incl. delay case)   │
└──────────────────────┴──────────────────────────────────┘
```

**Key design decision — the 7-type outreach spectrum (Layer 4):**

Not every message needs a product. The agent chooses from a spectrum ordered soft → commercial:

```
Soft ◄──────────────────────────────────────────► Commercial
  1           2           3          4          5         6        7
Relation-  Content/   Trend     Curated   Product   Event/   Service-
ship       Inspira-   Conver-   Preview   Sugges-   Experi-  led
Check-in   tion       sation              tion      ence
(no        (no        (product                      Invite
product)   product)   optional)
```

This prevents the most common CA agent failure: always forcing a product into every message.

---

## Step 2 — Live-Run the Agent

> *(Presenter runs: `python3 agent.py --all`)*

*(See live demo — runs 5 clients against Claude claude-sonnet-4-20250514, ~15 seconds per client.)*

The terminal will print a summary for each client as results come in:

```
正在为 陈雅琳 (C_102) 调用 Claude...
(Calling Claude for Chen Yalin, C_102...)

============================================================
  C_102  陈雅琳  (艺术圈女藏家)
         Chen Yalin  (Art Circle Female Collector)
============================================================
  Angle:      工艺纪录片延展 + 春季建筑感新作
              Craft Documentary Extension + Spring Architectural New Arrivals
  Type:       content_sharing
  Confidence: high

  --- Draft 1 [审美同行 / Aesthetic Peer] ---
  陈女士，您之前关注的那个面料工坊系列，本季有几件很有意思的作品到了。
  廓形和面料处理都很纯粹，我觉得您会喜欢这种表达方式。方便的话我拍几张细节图给您？
  (Ms. Chen, regarding the fabric atelier series you were interested in,
  we have a few intriguing new pieces this season. The silhouettes and
  fabric work are very pure — I think you'd appreciate this expression.
  Would it be convenient for me to send you some detail shots?)
```

---

## Step 3 — Show Output and Evidence


Let me walk through three representative outputs that demonstrate how the agent adapts its strategy across very different client profiles.

### 3.1 Output Summary Table

| Client | Persona | Tier | Outreach Type | Best Angle | Confidence |
|---|---|---|---|---|---|
| 陈雅琳 C_102 *(Chen Yalin)* | 艺术圈女藏家 *(Art Circle Collector)* | VVIP | content_sharing | 工艺纪录片延展 + 春季建筑感新作 *(Craft Documentary Extension + Spring Architectural New Arrivals)* | high |
| 周晓彤 C_205 *(Zhou Xiaotong)* | 社交媒体新世代 *(Gen-Z Social Native)* | Gold | curated_preview | Kelly Green迷你包到货 + Tenniscore新品 *(Kelly Green Mini Bag In Stock + Tenniscore New Arrivals)* | high |
| 林世恒 C_308 *(Lin Shiheng)* | 传统品味收藏家 *(Heritage Taste Collector)* | VIC | curated_preview | 慢美学工艺叙事 + 春季皮具预览 *(Slow Aesthetics Craft Narrative + Spring Leather Goods Preview)* | high |
| 赵思琳 C_412 *(Zhao Silin)* | 社交场红毯常客 *(Gala & Red Carpet Regular)* | VIC | curated_preview | 慈善晚宴礼服预览 + 新大佬风趋势 *(Charity Gala Gown Preview + Power Dressing Trend)* | high |
| 刘凯文 C_501 *(Liu Kaiwen)* | 效率至上科技高管 *(Efficiency-First Tech Executive)* | Platinum | product_suggestion | 轻量旅行鞋新品预览 *(New Lightweight Travel Shoes Preview)* | high |

### 3.2 Deep Dive: Evidence Traceability

**Case A — 陈雅琳 (VVIP, Art Collector)**

The agent chose `content_sharing` — NOT a direct product push. Why?

| Evidence Used | Source Field | Decision Impact |
|---|---|---|
| 点击品牌工坊纪录片：面料溯源 *(Clicked brand atelier documentary: fabric sourcing)* | `behavior_signals_90d.content_click` | → Chose "content sharing" as entry angle |
| 到店试了charcoal色oversized风衣，未购买 *(Visited store, tried charcoal oversized trench coat, did not purchase)* | `behavior_signals_90d.store_visit` | → Products are relevant but secondary |
| style: architectural, avant_garde | `style_profile` | → Matched to T05 (慢美学/匠心底蕴 / *Slow Aesthetics & Heritage Craft*) |
| 按廓形和面料买，不按潮流买 *(Buys by silhouette and fabric, not by trend)* | `product_affinity_notes` | → Frame product by craft, not trend |
| T05: 慢美学/匠心底蕴, rising *(Slow Aesthetics & Heritage Craft, rising)* | `trend_shortlist` | → Content angle, not commercial angle |

**Key agent behavior**: Despite having a product signal (tried coat but didn't buy), the agent chose a softer "content sharing" angle. It understood that this client wants to be treated as an "aesthetic peer" — 审美同行 — not a buyer. The message tone says "我觉得您会喜欢这种表达方式" *(I think you'd appreciate this form of expression)* — this feels like sharing art, not selling.

**Case B — 周晓彤 (Gold, Gen-Z Social)**

The agent chose `curated_preview` with high confidence. Why?

| Evidence Used | Source Field | Decision Impact |
|---|---|---|
| 主动问CA新一季运动鞋什么时候到 *(Proactively asked CA when new-season sneakers arrive)* | `behavior_signals_90d.message_to_ca` | → Direct request = strong signal |
| 收藏了kelly green迷你包 *(Wishlisted the kelly green colorway mini bag)* | `behavior_signals_90d.wishlist_add` | → Wishlist item in stock = action trigger |
| 小红书博主穿搭：tenniscore度假风 *(Clicked Xiaohongshu blogger post: tenniscore vacation style)* | `behavior_signals_90d.content_click` | → Style context confirmed |
| 收藏型买家，首发/限量敏感 *(Collector buyer, highly sensitive to first-drops and limited editions)* | `product_affinity_notes` | → Urgency framing is appropriate here |
| T03: 迷你包 × 声量配饰, peak *(Mini Bags & Statement Accessories, peak stage)* | `trend_shortlist` | → Trend validation |

**Key agent behavior**: Three converging signals (ask + wishlist + content click) = the agent confidently uses a direct product approach. The tone shifts to casual-excited — "晓彤！你要的那双新季运动鞋刚到...🎾" *(Xiaotong! The new-season sneakers you wanted just arrived, and the kelly green mini bag you saved is in stock 🎾)* — matching her Gen-Z persona. Compare this to 陈雅琳's formal "陈女士" — the agent adapts voice per client.

**Case C — 刘凯文 (Platinum, Tech Executive)**

The agent chose `product_suggestion` — the most direct approach.

| Evidence Used | Source Field | Decision Impact |
|---|---|---|
| 问有没有新的轻量旅行鞋，4月连续出差三周 *(Asked if there are new lightweight travel shoes; traveling for business 3 consecutive weeks in April)* | `behavior_signals_90d.message_to_ca` | → Explicit request with deadline |
| style: minimalist, tech_luxury, functional | `style_profile` | → Frame by specs, not aesthetics |
| category: travel_shoes, travel_accessories | `category_preference` | → Confirmed category match |
| T02: 高智感/松弛感, 技术面料 *(Smart Minimalism / Effortless Chic, technical fabric)* | `trend_shortlist` | → Trend supports functional angle |

**Key agent behavior**: The draft is ultra-concise — "单只280g，防皱透气...30分钟搞定" *(280g per shoe, wrinkle-resistant and breathable... done in 30 minutes)* — no brand storytelling, no trend narrative. The agent respected `sensitivity_flags`: "极度重视效率——不要浪费他的时间" *(Values efficiency extremely — do not waste his time)*. This is the shortest message across all 5 clients.

### 3.3 Cross-Client Adaptation Analysis

| Dimension | 陈雅琳 *(Chen Yalin)* | 周晓彤 *(Zhou Xiaotong)* | 林世恒 *(Lin Shiheng)* | 赵思琳 *(Zhao Silin)* | 刘凯文 *(Liu Kaiwen)* |
|---|---|---|---|---|---|
| **Tone** | 审美同行 *(Aesthetic Peer)* | excited_insider | 工艺叙事 *(Craft Narrative)* | 专业定制 *(Professional Bespoke)* | 直接高效 *(Direct & Efficient)* |
| **Message Length** | ~70 chars | ~60 chars | ~80 chars | ~70 chars | ~40 chars |
| **Product Framing** | Craft + silhouette | Collection + first-drop | Heritage story | Occasion fit | Specs + weight |
| **Trend Used** | T05 慢美学 *(Slow Aesthetics)* | T03 迷你包 *(Mini Bags)* | T05 慢美学 *(Slow Aesthetics)* | T04 新大佬风 *(Power Dressing)* | T02 高智感 *(Smart Minimalism)* |
| **CTA Style** | "拍几张细节图给您？" *(Shall I send you some detail shots?)* | "要不要我先给你留着？" *(Want me to hold it for you?)* | "为您单独预约时间" *(Arrange a private appointment)* | "我先选几件拍给您看？" *(Let me pick a few pieces to show you?)* | "43码现货" *(Size 43 in stock)* |

This table proves the agent is NOT using a one-size-fits-all template. Each output is genuinely personalized based on the specific intersection of client profile × behavioral signals × relevant trends.

---

## Step 4 — Show the Trace Log

> *(Presenter opens `run_log.json` or the Run Log Viewer)*

Each run logs:
- `run_id` + `timestamp` — when the agent ran
- `model` + `token_usage` — which LLM, how many tokens
- `input` — client_id + trend_ids fed into the agent
- `output.raw` — the full LLM response (for debugging)
- `output.parsed` — structured JSON output
- `trace.retrieved_sources` — which data files were used
- `trace.decision_output` — the final angle chosen
- `trace.evidence_used` — list of evidence citations
- `trace.confidence` + `trace.next_step` — decision metadata

*(Open the standalone viewer to show the interactive version with Chinese/English toggle.)*

---

## Step 5 — Show Feedback

> *(Presenter says:)*

We collected structured feedback from **5 external reviewers** using a standardized questionnaire covering usability, trust, brand alignment, tone, logic, and real-world practicality.

### 5.1 Quantitative Scores

| Reviewer | Immediate Usability (1–5) | Trust / Accuracy (1–5) | Brand Voice Alignment (1–5) |
|---|---|---|---|
| User 1 | 4 | 4 | 4.5 |
| User 2 | 4 | 3 | 4 |
| User 3 | 4 | 4.5 | 4.5 |
| User 4 | 5 | 3.5 | 4 |
| User 5 | 4 | 3 | 3 |
| **Average** | **4.2 / 5** | **3.6 / 5** | **4.0 / 5** |

**Key takeaway**: Usability is strong (4.2) — outputs are largely ready to use. Trust is the weakest dimension (3.6) — reviewers wanted more grounding and flagged product availability assumptions. Brand alignment is solid (4.0) but consistency needs improvement.

---

### 5.2 What Worked Well

- **High practical usability**: All 5 reviewers rated outputs 4+ on usability. User 4 gave 5/5 — *"I really like the approachability of the responses."*
- **Logic and flow**: All reviewers confirmed data-to-recommendation logic is consistent and easy to follow. The progression from client context → evidence → outreach angle → drafted message felt natural.
- **Personalization approach**: Reviewers appreciated that different clients received noticeably different tones. User 1: *"Overall they're solid and practical."*
- **Real-world executability**: All 5 confirmed the outputs are practically doable. User 2: *"It can be really helpful as an algorithm for specific things."*

---

### 5.3 Issues Identified

#### Issue 1 — Occasional AI-isms in Tone *(raised by Users 2, 3, 4, 5)*

Some phrasing felt slightly AI-generated — either too formal or using unnatural cadence for real WeChat conversation. User 3 specifically flagged:
> *"这个绿色真的太适合春天出片了" / "我觉得这套配起来特别适合你最近关注的那种tennis风～ — I don't know if it was my experience with AI or people are talking in a way that sounds like AI. The sequence of language doesn't appear in daily conversation often."*

User 1 suggested a concrete edit:
> *Original: "I've selected two pairs in black and gray and took photos for you"*
> *Revised: "I picked out two options in black and gray for you. Photos are on their way."*
> *"Still professional, just easier to read."*

**Implication**: The system prompt's "voice and tone" guardrails work but need tighter calibration — the agent should be given more natural, conversational WeChat examples in few-shots.

#### Issue 2 — Product Availability Assumptions *(raised by Users 4, 5)*

The agent sometimes assumes products are "in stock" and "available," which doesn't reflect how luxury retail actually works. User 5:
> *"For things like a mini Kelly or watches, I don't think an AI agent will know if it's available or not — these items are offered to clients in store and not readily available. Many luxury items are not 'available', it has to be offered first before purchase."*

User 4 also noted the `do_not_say` fields raised questions:
> *"The only 'weird' details I wonder where it gets them from are some of the things in the categories of 'Do Not Say'."*

**Implication**: The agent must distinguish between "suggest exploring this product category/style" vs. "this item is in stock." Product availability language needs a rule added to the guardrails: never assert availability unless explicitly provided in input data.

#### Issue 3 — All Runs Returned Zero Risk Flags *(raised by User 2)*

> *"Every part said no risk flags, which felt a bit off to me for an AI model."*

**Implication**: With signal-rich simulated test data, the agent correctly found no major risks. However, in a real deployment, the `risk_flags` field should surface more nuanced concerns (e.g., contact frequency approaching limit, inferred intent that lacks direct evidence). This ties directly to the Week 2 sparse-data stress test.

#### Issue 4 — Trust Gap: Missing Client-Side Evidence *(raised by Users 3, 4)*

User 4: *"I need maybe quotes from clients too — there are only quotes from CAs talking to clients. Could be good for privacy but credibility can be a little low."*

User 3 also questioned: *"The preferred time period — is it based on past chat history?"*

**Implication**: The agent's evidence citations reference internal JSON fields, which are opaque to end users. Adding a brief explanation of where each data point originated (e.g., "preferred time 10:00–12:00 is from client contact preference record") would improve transparency and trust.

#### Issue 5 — CA Needs Final Editorial Control *(raised by Users 1, 3)*

User 3: *"The CA should also have the right to revise the messages a bit according to real situations."*
User 1: *"A quick nod to a recent conversation or a known preference would go a long way. Even a small timing cue — like availability or a follow-up window — would make them feel more personal."*

**Implication**: The agent is correctly positioned as a **copilot, not an autopilot**. The output is a starting draft, not a final message. This should be made explicit in the UI — outputs are labeled as "draft for CA review" and the workflow should have an explicit Edit → Approve step before any message goes out.

---

### 5.4 Feedback Summary

| Theme | Verdict | Action Required |
|---|---|---|
| Usability & flow | ✅ Strong | Minor phrasing polish |
| Brand tone consistency | ⚠️ Good but uneven | Tighten few-shot examples; reduce AI-isms |
| Product availability language | ❌ Needs fix | Add guardrail: never assert stock/availability without input data |
| Risk flag quality | ⚠️ Too clean | Test with sparse/adversarial data to validate calibration |
| Evidence transparency | ⚠️ Opaque | Add source attribution to evidence citations |
| CA editorial control | ✅ By design | Make "draft for review" framing explicit in UI |

---

## Step 6 — Show Evaluation Metrics & Next Week Plan



### 6.1 Evaluation Metrics

| | Evidence Accuracy | Outreach Type | Tone Alignment | Guardrail Compliance | Confidence Calibration |
|---|---|---|---|---|---|
| **What it measures** | Every evidence_used item traces to a specific input field. No hallucinated facts. | Outreach type matches evidence strength (strong → product; weak → check-in; none → delay). | Message tone matches client persona, age, style, and sensitivity flags. | No FOMO, no fake intimacy, no `do_not_reference` violations, contact limits respected. | High confidence only when signals are strong; low/delay when data is sparse. |
| **Pass threshold** | 100% grounded — zero fabricated claims | Correct type for all runs with clear signals | No sensitivity flag violations in any draft | All 5 guardrail checks pass per run | High ↔ strong signals; Medium/Low ↔ weak data |
| **Target (Week 2)** | 100% | ≥ 95% correct across benchmark set | ≥ 95% rated "natural fit" by CA reviewer | 100% pass | Correct calibration on sparse-data test cases |
| **Current MVP** | ✅ 5/5 fully grounded | ✅ 5/5 correct | ✅ 5/5 tone appropriate | ✅ 5/5 all checks pass | ✅ All high — defensible (signal-rich test data) |

**Token efficiency**: ~7,600 tokens/run avg (6,800 input + 800 output) · ~$0.03 per client suggestion.

---

### 6.2 Next Week Plan

**1 — Cross-Module Data Integration**
Align with Module 2 & Module 4 teams to confirm shared client data schema. Obtain API access to their client database and connect it as the live input source for `client_memory`. Update the system prompt and input formatter to accommodate any schema differences from the current simulated JSON.

**2 — Scoring Agent + Automated Benchmark**
Build a scoring agent that runs batch evaluation against a 20+ client benchmark set and auto-scores each output across the 5 metrics above. Target: ≥ 95% satisfaction rate. The scoring agent will flag any run below threshold for manual review and produce a per-run scorecard appended to `run_log.json`.

**3 — Live Product Data Integration**
Investigate how to ingest LVMH new arrival data (via API, feed, or internal CMS export) and pass relevant products into the agent's context window alongside trends. This will replace the generic trend-matching approach with precise, real-time product recommendations tied to actual inventory.

---

*End of Demo Script*
