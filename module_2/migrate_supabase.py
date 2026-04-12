"""
migrate_supabase.py — Safe schema migration for module2_trend_shortlist.

Adds all Week 11 columns to the existing table. Safe to re-run:
each ALTER TABLE is wrapped in try/except — if the column already exists
(duplicate_column error code 42701) it prints "already exists, skipping".

Usage:
    cd /Users/kellyliu/Desktop/mvp_W10
    python module_2/migrate_supabase.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from supabase_client import get_conn, is_configured

NEW_COLUMNS = [
    # (column_name, sql_type, description)
    ("location",                      "TEXT DEFAULT 'China'",  "source city or region"),
    ("data_type",                     "TEXT",                  "'real', 'synthetic', or 'merged'"),
    ("subcategory",                   "TEXT",                  "inferred product subcategory"),
    ("client_persona_match_name",     "TEXT",                  "matched archetype name"),
    ("hero_product",                  "TEXT",                  "specific Celine product linked to trend"),
    ("hero_product_source",          "TEXT",                  "'extracted_from_posts' or 'llm_suggested'"),
    ("score_ca_conversational_utility", "NUMERIC(4,1)",        "Week 11 CA utility score 0-10"),
    ("score_language_specificity",    "NUMERIC(4,1)",          "Week 11 language specificity score 0-10"),
    ("score_client_persona_match",    "NUMERIC(4,1)",          "Week 11 client persona match score 0-10"),
    ("score_novelty",                 "NUMERIC(4,1)",          "Week 11 novelty score 0-10"),
    ("score_trend_velocity",          "NUMERIC(4,1)",          "Week 11 trend velocity score 0-10"),
    ("score_cross_run_persistence",   "NUMERIC(4,1)",          "Week 11 cross-run persistence score 0-10"),
    ("engagement_recency_pct",        "NUMERIC(5,1)",          "% of engagement from last 7 days"),
    ("low_signal_warning",            "BOOLEAN DEFAULT FALSE", "true if post_count was below 5"),
    ("no_date_signal",                "BOOLEAN DEFAULT FALSE", "true if no valid post dates found"),
    ("disqualifying_reason",          "TEXT",                  "reason trend was rejected if applicable"),
]

UNIQUE_CONSTRAINT = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_m2_shortlist_run_trend'
        AND conrelid = 'module2_trend_shortlist'::regclass
    ) THEN
        ALTER TABLE module2_trend_shortlist
        ADD CONSTRAINT uq_m2_shortlist_run_trend UNIQUE (run_id, trend_id);
        RAISE NOTICE 'Added unique constraint uq_m2_shortlist_run_trend';
    END IF;
END $$;
"""


def run_migration():
    if not is_configured():
        print("[ERROR] SUPABASE_PASSWORD not set — cannot connect. Check your .env file.")
        sys.exit(1)

    conn = get_conn()
    print(f"\nConnected to Supabase. Running migration on module2_trend_shortlist...\n")

    added = 0
    skipped = 0

    try:
        # Add each column
        for col_name, col_type, description in NEW_COLUMNS:
            sql = f"ALTER TABLE module2_trend_shortlist ADD COLUMN {col_name} {col_type};"
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
                conn.commit()
                print(f"  ✓ Added   {col_name:40s} ({description})")
                added += 1
            except Exception as e:
                conn.rollback()
                # 42701 = duplicate_column, 42P07 = duplicate_table — safe to skip
                if "42701" in str(e) or "already exists" in str(e).lower():
                    print(f"  – Skipped {col_name:40s} already exists")
                    skipped += 1
                else:
                    print(f"  ✗ ERROR   {col_name:40s} {e}")

        # Add unique constraint for upsert support
        print()
        try:
            with conn.cursor() as cur:
                cur.execute(UNIQUE_CONSTRAINT)
            conn.commit()
            print("  ✓ Unique constraint (run_id, trend_id) confirmed.")
        except Exception as e:
            conn.rollback()
            print(f"  – Unique constraint: {e}")

        print(f"\nMigration complete — {added} column(s) added, {skipped} already existed.\n")

    finally:
        conn.close()


if __name__ == "__main__":
    run_migration()
