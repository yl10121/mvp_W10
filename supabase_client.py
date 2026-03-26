"""
supabase_client.py — Global Supabase connection factory
=========================================================
All modules import this to get a database connection.
Credentials come from the root .env file.

Usage (in any module):
    from supabase_client import get_conn, insert_row, insert_rows

    conn = get_conn()
    insert_row(conn, "module1_trend_objects", {"run_id": "run_0001", ...})
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


# ── Load .env from the project root ──────────────────────────────
def _load_env():
    for env_path in [Path(__file__).parent / ".env",
                     Path(__file__).parent.parent / ".env"]:
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

_load_env()

SUPABASE_HOST     = os.environ.get("SUPABASE_HOST",     "aws-1-ap-northeast-1.pooler.supabase.com")
SUPABASE_PORT     = os.environ.get("SUPABASE_PORT",     "6543")
SUPABASE_DB       = os.environ.get("SUPABASE_DB",       "postgres")
SUPABASE_USER     = os.environ.get("SUPABASE_USER",     "postgres.krfdyudabrlmjixbdcxm")
SUPABASE_PASSWORD = os.environ.get("SUPABASE_PASSWORD", "")


# ── Connection factory ────────────────────────────────────────────
def get_conn():
    """
    Return a live psycopg2 connection to the Supabase Postgres database.
    Raises ImportError if psycopg2 is not installed.
    Raises ValueError if SUPABASE_PASSWORD is not set.
    """
    try:
        import psycopg2
    except ImportError:
        raise ImportError(
            "psycopg2 is not installed. Run:\n"
            "  pip install psycopg2-binary"
        )

    if not SUPABASE_PASSWORD:
        raise ValueError(
            "SUPABASE_PASSWORD is not set. Add it to your .env file:\n"
            "  SUPABASE_PASSWORD=your_password_here"
        )

    return psycopg2.connect(
        host=SUPABASE_HOST,
        port=int(SUPABASE_PORT),
        dbname=SUPABASE_DB,
        user=SUPABASE_USER,
        password=SUPABASE_PASSWORD,
        sslmode="require",
        connect_timeout=10,
    )


def is_configured() -> bool:
    """Return True if Supabase credentials are present."""
    return bool(SUPABASE_PASSWORD)


# ── Helper: insert a single row ───────────────────────────────────
def insert_row(conn, table: str, data: dict[str, Any]) -> int | None:
    """
    Insert `data` into `table`. JSONB columns are auto-serialized.
    Returns the new row's id, or None on failure.
    """
    import psycopg2.extras
    # Serialize any dict/list values to JSON strings for JSONB columns
    clean = {k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
             for k, v in data.items()}

    cols   = ", ".join(clean.keys())
    placeholders = ", ".join(["%s"] * len(clean))
    sql    = f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) RETURNING id;"

    try:
        with conn.cursor() as cur:
            cur.execute(sql, list(clean.values()))
            row = cur.fetchone()
            conn.commit()
            return row[0] if row else None
    except Exception as e:
        conn.rollback()
        print(f"  [DB WARN] insert_row({table}) failed: {e}")
        return None


def insert_rows(conn, table: str, rows: list[dict[str, Any]]) -> int:
    """Bulk insert list of dicts. Returns number of rows inserted."""
    inserted = 0
    for row in rows:
        if insert_row(conn, table, row) is not None:
            inserted += 1
    return inserted


def upsert_row(conn, table: str, data: dict[str, Any],
               conflict_col: str = "run_id") -> int | None:
    """
    Insert or update a row using ON CONFLICT DO UPDATE.
    `conflict_col` is the column to check for conflicts.
    """
    clean = {k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
             for k, v in data.items()}

    cols         = ", ".join(clean.keys())
    placeholders = ", ".join(["%s"] * len(clean))
    updates      = ", ".join(f"{k}=EXCLUDED.{k}" for k in clean if k != conflict_col)
    sql = (
        f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) "
        f"ON CONFLICT ({conflict_col}) DO UPDATE SET {updates} RETURNING id;"
    )
    try:
        with conn.cursor() as cur:
            cur.execute(sql, list(clean.values()))
            row = cur.fetchone()
            conn.commit()
            return row[0] if row else None
    except Exception as e:
        conn.rollback()
        print(f"  [DB WARN] upsert_row({table}) failed: {e}")
        return None
