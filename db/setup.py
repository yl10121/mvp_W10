#!/usr/bin/env python3
"""
db/setup.py — Run all Supabase schema migrations
==================================================
Creates every module's tables if they don't already exist.
Safe to run multiple times (all statements use IF NOT EXISTS).

Usage:
    python3 db/setup.py
    python3 db/setup.py --module 1        # only module 1
    python3 db/setup.py --dry-run         # print SQL without executing
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

# Add repo root to path so supabase_client imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from supabase_client import get_conn, is_configured

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

MODULE_FILES = {
    1: "module1.sql",
    2: "module2.sql",
    3: "module3.sql",
    4: "module4.sql",
    5: "module5.sql",
}

# Extra migrations run immediately after the main file for that module (same module number).
MODULE_EXTRA_FILES = {
    1: ["module1_brand_products.sql"],
}


def run_migration(conn, sql_path: Path, dry_run: bool = False):
    sql = sql_path.read_text(encoding="utf-8")
    # Split on semicolons to execute statement by statement
    statements = [s.strip() for s in sql.split(";") if s.strip()]

    print(f"\n  [{sql_path.name}] {len(statements)} statements")
    for stmt in statements:
        if dry_run:
            print(f"  [DRY-RUN] {stmt[:80]}…")
            continue
        try:
            with conn.cursor() as cur:
                cur.execute(stmt)
            conn.commit()
            print(f"  [OK] {stmt[:70].replace(chr(10), ' ')}…")
        except Exception as e:
            conn.rollback()
            print(f"  [WARN] {e} — statement: {stmt[:60]}")


def main():
    parser = argparse.ArgumentParser(description="Run Supabase migrations")
    parser.add_argument("--module", type=int, choices=[1, 2, 3, 4, 5],
                        help="Only run migration for this module number")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print SQL without executing")
    args = parser.parse_args()

    if not is_configured() and not args.dry_run:
        print("ERROR: SUPABASE_PASSWORD not set in .env — cannot connect.")
        print("  Add to your .env:  SUPABASE_PASSWORD=your_password_here")
        sys.exit(1)

    modules = {args.module: MODULE_FILES[args.module]} if args.module else MODULE_FILES

    print("=" * 60)
    print("Supabase Schema Setup")
    print(f"Modules : {list(modules.keys())}")
    print(f"Dry run : {args.dry_run}")
    print("=" * 60)

    conn = None if args.dry_run else get_conn()

    for mod_num, filename in modules.items():
        sql_path = MIGRATIONS_DIR / filename
        if not sql_path.exists():
            print(f"\n[SKIP] {sql_path} not found")
            continue
        print(f"\n[MODULE {mod_num}] Running {filename}…")
        run_migration(conn, sql_path, dry_run=args.dry_run)
        for extra in MODULE_EXTRA_FILES.get(mod_num, []):
            ep = MIGRATIONS_DIR / extra
            if not ep.exists():
                print(f"\n[SKIP] {ep.name} not found")
                continue
            print(f"\n[MODULE {mod_num}] Running {extra}…")
            run_migration(conn, ep, dry_run=args.dry_run)

    if conn:
        conn.close()

    print("\n[DONE] All migrations completed.")


if __name__ == "__main__":
    main()
