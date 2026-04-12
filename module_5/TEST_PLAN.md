# Module 5 — Testing Plan (Weeks 11–12)

## 1. Testing Objectives

The goal of our testing phase in Weeks 11 and 12 is to move beyond "making it work" and prove that our AI outreach drafts are useful for LVMH staff. Specifically:
- Would a real Client Advisor (CA) trust the AI to draft messages to their VIPs?
- Do the messages feel natural, or too "robotic"?
- What would a CA change before sending?

## 2. Target Reviewers (D1)

**Target: 3–5 real reviewers over Weeks 11–12**

| Role | Relevance | Target # |
|------|-----------|---------|
| Client Advisor (CA) | Primary user of the tool; daily WeChat outreach | 2 |
| CA Manager / Boutique Manager | Approves CA communication standards | 1 |
| CRM / Clienteling Lead | Understands client data + brand voice guidelines | 1 |
| Social Media Lead | Understands WeChat tone + content strategy | 1 |

**Proxy Plan**: If direct access to LVMH staff is limited, we will use peers with luxury retail experience (e.g., former LVMH interns, luxury brand trainees) as proxies. They must demonstrate familiarity with CA workflows and brand communication standards.

## 3. The 10-Minute Test Script (D2)

Each session uses this structured flow:

### Step 1 — Show Input (30 seconds)
Show the tester a real "Client Memory" object (e.g., BENCH_001 林婉清) and explain:
- What information the CA recorded about this client
- Which trend signals are available this week

### Step 2 — Run the Module (30–60 seconds)
Live-trigger Module 5 agent:
```bash
python3 module_5/agent.py --clients BENCH_001
```
Show the terminal output in real time.

### Step 3 — Show Output + Evidence (2 minutes)
Walk through the generated output:
- The outreach angle chosen and why
- The WeChat draft(s)
- The `evidence_used` field — showing every claim traces back to real client data
- The `confidence` score and `risk_flags`

Emphasize: *"The agent cites its evidence — it's not guessing."*

### Step 4 — Ask 3 Questions (5 minutes)

**Required questions:**

1. **Usefulness / Quality (1–5)**
   > "On a scale of 1 to 5, how useful is this output for your daily work as a CA?"

2. **Trust (1–5)**
   > "On a scale of 1 to 5, do you trust that the AI correctly used this client's information?"

3. **Constructive Critique (open text)**
   > "What is missing, wrong, or feels risky for the brand in this output?"

### Step 5 — Capture Rating + Quote (2 minutes)
Record:
- Numerical scores for all 3 questions
- One specific quote for Week 13 presentation
- One concrete suggested edit (if any)

## 4. Booked Sessions (D3)

| Session | Date & Time | Role | Status |
|---------|------------|------|--------|
| Session 1 | April 7 @ 10:00 AM | CA Manager | Pending confirmation |
| Session 2 | April 8 @ 2:30 PM | Social Media Lead | Pending confirmation |
| Session 3 | April 9 @ 11:00 AM | Luxury Retail Proxy | Booked |
| Session 4 | April 10 @ 4:00 PM | CRM Specialist | Pending confirmation |

## 5. Week 11–12 Timeline

| Week | Action |
|------|--------|
| Week 11 | Run 4 sessions → identify top failure → implement 1 prompt fix → re-run eval |
| Week 12 | Freeze code → compile metrics + quotes → prepare Week 13 evidence deck |
| Week 13 | Present pipeline + proof + "what LVMH needs next" |
