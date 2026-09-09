"""Apply SQL migrations in order (§103: database migrations).

Usage: python scripts/apply_migrations.py
Records applied migrations in schema_migrations; safe to re-run.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import get_db  # noqa: E402

MIGRATIONS_DIR = PROJECT_ROOT / "app" / "db" / "migrations"


def main() -> None:
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        print("No migrations found.")
        return
    applied = 0
    with get_db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
            migration  TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""")
    for path in files:
        sql = path.read_text(encoding="utf-8")
        with get_db() as conn:
            already = conn.execute(
                "SELECT 1 FROM schema_migrations WHERE migration = ?", (path.name,)
            ).fetchone()
            if already:
                print(f"  = {path.name} (already applied)")
                continue
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations (migration) VALUES (?)", (path.name,)
            )
        applied += 1
        print(f"  + {path.name}")
    print(f"Done. {applied} migration(s) applied.")


if __name__ == "__main__":
    main()
