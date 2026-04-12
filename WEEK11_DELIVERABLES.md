# Week 11 — Course deliverables (Modules 1–3 + org-wide)

This file maps the instructor requirements to **what to save in this repo** and **how to hit numeric thresholds**.

---

## Deliverable 1 — Real-data batch run (Modules 1–3)

| Requirement | What it means here | How to satisfy |
|---------------|-------------------|----------------|
| **Module 1: ≥200 posts** | Live XHS scrape (or approved real export) with **≥200 posts** in the saved dataset | Run `xhs_scraper_live.py` with enough keywords / scroll depth / runs until `xhs_posts.json` (or raw export) has ≥200 posts. Record **dataset ID** = run folder name + commit hash or `run_id` from logs. |
| **Module 2: ≥30 trend objects** | **Trend objects** come from **Module 1** (`*_trend_objects.json`), not the Module 2 shortlist count | Run `xhs_trend_builder.py` so the **trend_objects** array has **≥30** items. Tune clustering / min cluster size if needed. Module 2 then filters/scores that set. |
| **Module 3: ≥10 trend cards** | Final CA brief cards (markdown + HTML) | Ensure Module 2 shortlist has **≥10** trends available to Module 3 (`MAX_SHORTLIST` in Module 2 is already high enough). Set **`M3_TOP_N=10`** (or `--top-n 10`) so Module 3 generates up to **10** cards after filtering. If fewer than 10 pass Module 3’s city/failure rules, fix inputs or relax filters for the demo run only (document that). |

**You must save**

| Artifact | Suggested location |
|----------|---------------------|
| **Input dataset ID + date range** | One line in `feedback_log.csv` `notes` column or a small `runs/week11_batch_meta.json` (fields: `dataset_id`, `start_date`, `end_date`, `scrape_timestamp`, `source`: live vs export) |
| **Outputs** | `module_1/outputs/…`, `module_2/outputs/output_shortlist.json`, `module_3/trend_brief_agent/trend_cards_*_*.md` and `.html` |
| **Run log / trace** | `module_2/outputs/run_log.json`, `module_3/trend_brief_agent/run_log.json`, plus Supabase rows if enabled |

**Env for Week 11 card count**

```bash
# .env
M3_TOP_N=10
```

**Module 3 CLI**

```bash
cd module_3/trend_brief_agent
python3 agent.py --brand "Louis Vuitton" --city "Shanghai" --top-n 10
```

---

## Deliverable 2 — Real reviewer sessions (≥3 per module)

| Track | Who counts |
|-------|------------|
| **Modules 1–3** | Clienteling, social, retail ops, CA manager, ex-CA, brand marketing |
| **Modules 4–5** | CA, CA manager, clienteling ops, WeCom outreach experience |

If you use a **proxy role**, log: role used, why credible, limitation (same columns as in `feedback_log.csv`).

---

## Deliverable 3 — Logged feedback (non-negotiable)

Use the shared file **`feedback_log.csv`** at the repo root (one row per session).

**Per session, capture**

- Usefulness / quality **1–5**
- Trust **1–5**
- **One verbatim quote**
- **One concrete change request**
- **Time-to-evaluate** (minutes or seconds — use `time_to_evaluate_minutes` or put seconds in `notes`)

Fill `module` as `module_1`, `module_2`, `module_3`, etc.

---

## Deliverable 4 — One “fail case pack” (per team)

Create a small folder, e.g. **`fail_case_pack/`**, with:

| Item | Contents |
|------|----------|
| **Bad output** | Screenshot and/or paste of one bad card, trend object, or post cluster |
| **Why it failed** | One sentence |
| **Fix next week** | One sentence |

See `fail_case_pack/README.md` for a template.

---

## Quick checklist

- [ ] Batch run with real (or approved exported) XHS data; thresholds: **200+ posts, 30+ trend objects, 10+ cards**
- [ ] Saved: meta (ID + date range), outputs, run logs
- [ ] **≥3 reviewer sessions per module** logged in **`feedback_log.csv`**
- [ ] **`fail_case_pack/`** filled for Deliverable 4
- [ ] If blocked: contact course staff **before** the weekend before **Monday 13th** (per instructor message)
