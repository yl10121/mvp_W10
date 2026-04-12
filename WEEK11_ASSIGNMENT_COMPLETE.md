# Week 11 — Full assignment & completion log (MVP / Agent repo)

This document restates the **instructor Week 11 brief**, records **what this repository implements**, and **links** to the concrete files. Scope: **Module 1 is documented in full**; **Modules 2–5** are noted where the pipeline or teammates must finish the same rubric.

**Module 1 Week 11 bundle (single folder):** [`module_1/week11/README.md`](./module_1/week11/README.md)

---

## Part A — Full assignment (verbatim structure)

### Deliverable 1 — Real-data batch run (required for Modules 1–3)

- Modules 1–3 must run on **real XHS market data**.
- **Module 1:** ≥200 posts  
- **Module 2:** ≥30 trend objects  
- **Module 3:** ≥10 final trend cards/scripts  

**Output you must save:**

- the input **dataset ID** / **date range**  
- the **outputs** (objects/cards)  
- the **run log** (trace)  

If you can’t pull data directly, you may use a **real exported dataset** (screenshot/csv/json) as long as it’s market data and the volume threshold is met.

---

### Deliverable 2 — Real reviewer sessions (minimum 3 per module)

Each module must complete **at least 3 reviewer sessions** this week.

**Who counts as “real”**

- **For Modules 1–3 (trend):** clienteling / social / retail ops / CA manager / ex-CA / brand marketing  
- **For Modules 4–5 (memory/outreach):** CA / CA manager / clienteling ops / someone who has done WeCom outreach  

If you can’t access the perfect role, you must state:

- what **proxy role** you used  
- why it’s **credible**  
- what **limitation** it introduces  

---

### Deliverable 3 — Logged feedback (non-negotiable)

For **every** session, log:

- **Usefulness/Quality** (1–5)  
- **Trust** (1–5)  
- **One verbatim quote**  
- **One concrete change request**  
- **Time-to-evaluate** (seconds/minutes)  

Save it in **`feedback_log.csv`** (shared format across teams).

---

### Deliverable 4 — One “fail case pack”

Each team must produce **one** failure pack:

- one **bad output example** (screenshot)  
- **why it failed** (one sentence)  
- **what fix you’ll try next week** (one sentence)  

If any challenge: contact course staff **ASAP** (don’t wait until the weekend before **Monday 13th**).

---

## Part B — What we did in this repo (with links)

### Deliverable 1 — Batch run & artifacts

| Requirement | What we did | Link / path |
|-------------|-------------|-------------|
| Real XHS market data | Scraped / exported posts stored as JSON; used as Module 1 input | [`module_1/data/xhs_posts.json`](./module_1/data/xhs_posts.json) |
| Run configuration | Keywords, caps, clustering options (incl. Week 11 thresholds) | [`module_1/data/run_config.json`](./module_1/data/run_config.json) |
| ≥200 posts | Batch sized to **200** posts | Same file as above; count verified at runtime |
| ≥30 trend objects (course wording; produced in **Module 1** pipeline as trend clusters) | **`force_equal_engagement_bins`** + `top_k_trends` in config; 30 objects in named run | [`module_1/outputs/runs/run_0036_trend_objects.json`](./module_1/outputs/runs/run_0036_trend_objects.json) *(re-run may create `run_XXXX`; see latest under [`module_1/outputs/runs/`](./module_1/outputs/runs/))* |
| Dataset ID + date range + paths | Machine-readable meta | [`module_1/deliverables/week11_batch_meta.json`](./module_1/deliverables/week11_batch_meta.json) |
| Human-readable D1 checklist | What to zip / submit for Module 1 | [`module_1/deliverables/DELIVERABLE_1_README.md`](./module_1/deliverables/DELIVERABLE_1_README.md) |
| Run log + trace | Per-run JSON + CLI trace | [`module_1/outputs/runs/run_0036_run_log.json`](./module_1/outputs/runs/run_0036_run_log.json), [`module_1/outputs/runs/run_0036_trace.log`](./module_1/outputs/runs/run_0036_trace.log) |
| Latest copies (convenience) | Symlink-style “latest” outputs in `outputs/` | [`module_1/outputs/trend_objects.json`](./module_1/outputs/trend_objects.json), [`module_1/outputs/run_log.json`](./module_1/outputs/run_log.json) |
| Pipeline / Supabase / README | Global orchestration & DB | [`main.py`](./main.py), [`README.md`](./README.md), [`supabase_client.py`](./supabase_client.py) |
| Extra Week 11 notes | Older umbrella doc | [`WEEK11_DELIVERABLES.md`](./WEEK11_DELIVERABLES.md) |

**Modules 2–3 (same Deliverable 1, rest of team):** run [`module_2/agent.py`](./module_2/agent.py) then Module 3 with `M3_TOP_N=10` (see [`module_3/trend_brief_agent/agent.py`](./module_3/trend_brief_agent/agent.py), [`.env.example`](./.env.example)). Outputs live under `module_2/outputs/` and `module_3/trend_brief_agent/` — **complete those runs and archive** for full M1–M3 Deliverable 1.

---

### Deliverable 2 — Reviewer sessions (Module 1)

| Requirement | What we did | Link / path |
|-------------|-------------|-------------|
| ≥3 sessions **for Module 1** | Three boutique interviews (Tiffany, Cartier, Fendi) transcribed; roles fit “clienteling / retail” | Source: [`module_1/interviews/tiffany.md`](./module_1/interviews/tiffany.md) |
| Optional extra voice | Stone Island (English) — optional context | [`module_1/interviews/stone-island.md`](./module_1/interviews/stone-island.md) |
| Summary (Module 1 only) | Who / quotes / no proxy | [`module_1/interviews/DELIVERABLE_2_3_EXTRACT.md`](./module_1/interviews/DELIVERABLE_2_3_EXTRACT.md) |

**Other modules (2–5):** each still needs **its own** 3+ sessions logged by the responsible teammates.

---

### Deliverable 3 — `feedback_log.csv`

| Requirement | What we did | Link / path |
|-------------|-------------|-------------|
| Shared CSV with required columns | **Three rows**, all **`module_1`**, with usefulness, trust, verbatim quote, change request, minutes | [`feedback_log.csv`](./feedback_log.csv) |

Merge with other modules’ rows in the same file when the team consolidates for submission.

---

### Deliverable 4 — Fail case pack

| Requirement | What we did | Link / path |
|-------------|-------------|-------------|
| Folder + template | Instructions | [`fail_case_pack/README.md`](./fail_case_pack/README.md) |
| One-sentence failure + fix | **Module 1:** LLM enabled but no API key → **0** LLM labels, duplicate heuristic labels | [`fail_case_pack/failure_notes.md`](./fail_case_pack/failure_notes.md) |
| Screenshot of bad output | Stylized capture of the warning + duplicate labels | [`fail_case_pack/screenshot.png`](./fail_case_pack/screenshot.png) |

---

## Part C — Module 1 “done?” checklist (quick)

- [x] **200** posts in [`module_1/data/xhs_posts.json`](./module_1/data/xhs_posts.json)  
- [x] **30** trends in [`module_1/outputs/runs/run_0036_trend_objects.json`](./module_1/outputs/runs/run_0036_trend_objects.json)  
- [x] Meta + README + run log + trace paths match what you submit (`run_0036`)  
- [x] **3** reviewer sessions documented + **3** rows in [`feedback_log.csv`](./feedback_log.csv) for `module_1`  
- [x] **Fail pack** filled ([`failure_notes.md`](./fail_case_pack/failure_notes.md) + [`screenshot.png`](./fail_case_pack/screenshot.png))  
- [ ] **Team:** Module 2–3 batch run + **≥10** cards + their logs; Modules 4–5 sessions if in scope  

---

## Part D — Repo map (related code)

| Area | Entry point |
|------|-------------|
| **Module 1 Week 11 (all deliverables indexed)** | [`module_1/week11/README.md`](./module_1/week11/README.md) |
| Module 1 scrape | [`module_1/xhs_scraper_live.py`](./module_1/xhs_scraper_live.py) |
| Module 1 trend builder | [`module_1/xhs_trend_builder.py`](./module_1/xhs_trend_builder.py) |
| Week 11 improvement ideas | [`module_1/SPEC_WEEK11_IMPROVEMENTS.md`](./module_1/SPEC_WEEK11_IMPROVEMENTS.md) |
| Full pipeline | [`main.py`](./main.py) |

---

*Last updated to match repo layout and `week11_batch_meta.json` (run `run_0036`). If you re-run the trend builder, update Part B links to the new `run_XXXX_*` files or refresh the meta JSON.*
