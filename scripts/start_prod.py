"""Start the production server.

Usage: python scripts/start_prod.py
Reads PORT from the environment (platforms inject it); defaults to 8000.
APP_BASE_URL is derived from PORT unless set explicitly, keeping share links correct.

First-boot bootstrap (all steps idempotent — safe on every restart):
  1. apply_migrations.py       creates/updates the schema
  2. app/db/seed_demo_data.py  reference data + admin bootstrap (honors ADMIN_EMAIL/ADMIN_PASSWORD)
  3. AUTO_REGISTER_SOURCES=1   registers the real ATS/sitemap sources
  4. INITIAL_CRAWL=1           runs one crawl so the site is not empty on first view
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

_port = int(os.getenv("PORT", "8000"))
# Must be set BEFORE importing the app: settings are read at import time.
os.environ.setdefault("APP_BASE_URL", f"http://127.0.0.1:{_port}")


def _run(script: str) -> None:
    print(f"[bootstrap] {script}")
    result = subprocess.run(
        [sys.executable, script], cwd=str(PROJECT_ROOT),
        env=os.environ.copy(), check=False,
    )
    if result.returncode != 0:
        print(f"[bootstrap] WARNING: {script} exited with {result.returncode}; continuing")


def bootstrap() -> None:
    _run("scripts/apply_migrations.py")
    _run(os.path.join("app", "db", "seed_demo_data.py"))
    if os.getenv("AUTO_REGISTER_SOURCES") == "1":
        _run("scripts/register_real_sources.py")
    if os.getenv("INITIAL_CRAWL") == "1":
        # Non-blocking: the crawl can take minutes; the server must bind its port
        # immediately to satisfy platform health checks.
        data_dir = PROJECT_ROOT / "data"
        data_dir.mkdir(exist_ok=True)
        crawl_log = open(data_dir / "crawl-boot.log", "ab")  # noqa: SIM115 — lives for process lifetime
        subprocess.Popen(
            [sys.executable, "scripts/crawl_once.py"], cwd=str(PROJECT_ROOT),
            env=os.environ.copy(), stdout=crawl_log, stderr=subprocess.STDOUT,
        )
        print("[bootstrap] initial crawl started in background (data/crawl-boot.log)")


def main() -> None:
    bootstrap()
    import uvicorn  # noqa: PLC0415 — after bootstrap so settings/env are final

    from app import create_app  # noqa: PLC0415

    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=_port, log_level="info")


if __name__ == "__main__":
    main()
