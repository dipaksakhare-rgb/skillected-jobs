"""Force-crawl real sources from the CLI.

Usage:
  python scripts/crawl_once.py                 # all real sources (forced)
  python scripts/crawl_once.py 17 18 19        # specific source_ids (forced)
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core import database as db  # noqa: E402
from app.crawler.ingest import run_crawl  # noqa: E402


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    args = sys.argv[1:]
    if args:
        ids = [int(a) for a in args]
    else:
        ids = [r["source_id"] for r in db.query_all(
            """SELECT s.source_id FROM career_sources s
               JOIN companies c ON c.company_id = s.company_id
               WHERE c.is_demo = 0 AND s.active = 1""")]
    print(f"Force-crawling {len(ids)} source(s): {ids}")
    report = run_crawl(trigger="manual", source_ids=ids or None)
    print(f"sources={report['sources']} discovered={report['discovered']} "
          f"published={report['new']} review={report['review']} "
          f"dupes={report['duplicates']} rejected={report['rejected']} "
          f"pune={report['pune']} fresher={report['fresher']} errors={report['errors']}")


if __name__ == "__main__":
    main()
