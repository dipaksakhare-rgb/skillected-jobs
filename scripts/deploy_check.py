"""Pre-deployment sanity checks for Skillected Jobs (§103).

Usage: python scripts/deploy_check.py
Exit code 0 = safe to deploy; 1 = fix the reported problems first.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

OK = "[ok]"
BAD = "[!!]"
WARN = "[?]"


def main() -> int:
    problems: list[str] = []
    warnings: list[str] = []

    env = os.getenv("APP_ENV", "development")
    secret = os.getenv("APP_SECRET", "")
    db_url = os.getenv("DATABASE_URL", "sqlite:///data/skillected.db")

    print("Skillected Jobs — deployment check")
    print(f"  APP_ENV        = {env}")
    print(f"  APP_BASE_URL   = {os.getenv('APP_BASE_URL', '(default localhost)')}")
    print(f"  DATABASE_URL   = {'postgres (set)' if db_url.startswith('postgres') else db_url}")
    print()

    if env == "production":
        if not secret or len(secret) < 32:
            problems.append("APP_SECRET must be set to 32+ random chars in production")
        elif secret == "dev-only-secret-change-me":
            problems.append("APP_SECRET is still the development default")
        admin_pw = os.getenv("ADMIN_PASSWORD", "ChangeMe!Admin1")
        if admin_pw == "ChangeMe!Admin1":
            problems.append("ADMIN_PASSWORD is still the development default")
        if not os.getenv("APP_BASE_URL", "").startswith("https://"):
            problems.append("APP_BASE_URL must be an https:// URL in production")
        if db_url.startswith("sqlite"):
            warnings.append("SQLite keeps everything on one disk and one process — fine to "
                            "start, but Postgres is the spec target (§79) and survives "
                            "redeploys; set DATABASE_URL when ready")
    else:
        if not secret or len(secret) < 32:
            warnings.append("APP_SECRET is unset/short — required before APP_ENV=production")

    # Imports must succeed with the production dependency set.
    try:
        from app import create_app  # noqa: F401
        app = create_app()
        routes = len(app.routes)
        print(f"{OK} application factory imports cleanly ({routes} routes)")
    except Exception as exc:  # noqa: BLE001
        problems.append(f"application failed to build: {exc}")

    # Migrations must be present and parseable.
    migrations = sorted((PROJECT_ROOT / "app" / "db" / "migrations").glob("*.sql"))
    if migrations:
        print(f"{OK} {len(migrations)} migration file(s) found")
    else:
        problems.append("no migrations found in app/db/migrations")

    for w in warnings:
        print(f"{WARN} {w}")
    for p in problems:
        print(f"{BAD} {p}")

    if problems:
        print("\nResult: NOT ready to deploy — fix the items above, then re-run.")
        return 1
    print("\nResult: ready to deploy. Set these env vars on the host:")
    print("  APP_ENV=production  APP_SECRET=<32+ random>  ADMIN_PASSWORD=<strong>")
    print("  ADMIN_EMAIL=<you>  APP_BASE_URL=https://<your-domain>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
