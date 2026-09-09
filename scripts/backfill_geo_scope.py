"""One-time scope backfill: enforce Maharashtra-only visibility on existing rows.

Idempotent — safe to re-run (Render's fresh databases are already scope-correct
because the ingestion gate filters at crawl time; this script repairs older data).

  1. Re-derive city/state for jobs with a location string via the geo service.
  2. Archive out-of-scope jobs (other states / countries / unknown / bare Remote):
     job_status='draft' + verification_status='rejected' — hidden from every
     public query and excluded from stats, but preserved for audit (§103).
  3. Re-evaluate the fresher flag with word-boundary rules (fixes 'get' matching
     'budget'/'target').
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core import database as db  # noqa: E402
from app.crawler.ingest import is_fresher_friendly, parse_experience  # noqa: E402
from app.services import geo  # noqa: E402


def main() -> None:
    rows = db.query_all(
        "SELECT job_id, job_title, location, city, state FROM jobs "
        "WHERE job_status='active' AND is_demo=0")
    rescope = out_scope = 0
    for r in rows:
        job = dict(r)
        # 1) Re-derive canonical city when we have any location text.
        new_city, new_state = geo.normalize_location(job.get("location")) or (None, None)
        if new_city:
            if new_city != job["city"] or (new_state or "") != (job["state"] or ""):
                db.execute("UPDATE jobs SET city=?, state=? WHERE job_id=?",
                           (new_city, new_state, job["job_id"]))
                rescope += 1
        # 2) Archive everything without a canonical city (out of scope).
        if not new_city:
            db.execute(
                "UPDATE jobs SET job_status='draft', verification_status='rejected' "
                "WHERE job_id=?", (job["job_id"],))
            out_scope += 1

    # 3) Fresher flag re-evaluation (word-boundary fix).
    refresh = 0
    for r in db.query_all(
            "SELECT job_id, job_title, job_description, experience_min FROM jobs "
            "WHERE job_status='active'"):
        job = dict(r)
        exp_min = job["experience_min"]
        if exp_min is None:
            parsed, _ = parse_experience(job["job_title"], job["job_description"] or "")
            exp_min = parsed
        flag = 1 if is_fresher_friendly(job["job_title"], exp_min) else 0
        db.execute("UPDATE jobs SET is_fresher_friendly=? WHERE job_id=?",
                   (flag, job["job_id"]))
        refresh += 1

    live = db.query_one(
        "SELECT COUNT(*) AS c FROM jobs WHERE job_status='active' AND is_demo=0")
    mh = db.query_one(
        "SELECT COUNT(*) AS c FROM jobs WHERE job_status='active' AND state='Maharashtra'")
    print(f"Backfill done: rescoped={rescope} archived_out_of_scope={out_scope} "
          f"fresher_re-evaluated={refresh}")
    print(f"Now active: {live['c']} real jobs ({mh['c']} in Maharashtra).")


if __name__ == "__main__":
    main()
