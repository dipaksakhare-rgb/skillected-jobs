"""Crawl scheduling + §53 report retrieval.

The scheduler is frequency-agnostic (§89): it simply runs due sources whenever
invoked. In dev this is a background thread started with the app; in production
the same `run_due_crawls()` is called from cron/Celery/queue worker without any
code change.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

from app.crawler.ingest import run_crawl, run_expiry_check
from app.core import database as db
from app.core.config import get_settings

settings = get_settings()

_scheduler_thread: threading.Thread | None = None
_stop = threading.Event()


def run_due_crawls() -> dict:
    """Run the ingestion cycle over all due sources, then the expiry check."""
    report = run_crawl(trigger="scheduled")
    expiry = run_expiry_check()
    report["expiry"] = expiry
    return report


def last_report() -> dict | None:
    row = db.query_one("SELECT * FROM crawl_runs ORDER BY run_id DESC LIMIT 1")
    return dict(row) if row else None


def report_history(limit: int = 10) -> list[dict]:
    return [dict(r) for r in db.query_all(
        "SELECT * FROM crawl_runs ORDER BY run_id DESC LIMIT ?", (limit,))]


def _loop(interval_seconds: int) -> None:
    """Scheduler loop: poll for due sources on a short cadence; crawl when due."""
    while not _stop.is_set():
        try:
            run_due_crawls()
        except Exception:  # noqa: BLE001 — scheduler must survive any failure (§82)
            import logging
            logging.getLogger("skillected.scheduler").exception("crawl cycle failed")
        _stop.wait(interval_seconds)


def start_scheduler(interval_seconds: int | None = None) -> None:
    """Start the background scheduler unless disabled via env (SKIP_SCHEDULER=1)."""
    global _scheduler_thread
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    if settings.app_env == "test" or os_environ_flag():
        return
    interval = interval_seconds or 300  # poll every 5 min; sources have own cadence
    _stop.clear()
    _scheduler_thread = threading.Thread(target=_loop, args=(interval,),
                                         name="skillected-scheduler", daemon=True)
    _scheduler_thread.start()


def os_environ_flag() -> bool:
    import os
    return os.getenv("SKIP_SCHEDULER", "").lower() in ("1", "true", "yes")


def stop_scheduler() -> None:
    _stop.set()
