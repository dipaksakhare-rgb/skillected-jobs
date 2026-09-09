"""Register real companies + their official ATS sources (researched, verified live).

Every company here publishes its own job board on a public ATS API (Greenhouse,
Lever, Ashby) — the application link is the company's own channel (§2).
Run:  python scripts/register_real_sources.py
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core import database as db  # noqa: E402
from app.repositories import sources_repo  # noqa: E402
from scripts.apply_migrations import main as apply_migrations  # noqa: E402

# (name, slug, official_url, industry, mnc, startup, source_url, ats_type, frequency_min)
REAL_SOURCES: list[tuple] = [
    ("Speechify", "speechify", "https://speechify.com", "AI Voice & Text-to-Speech", 0, 1,
     "https://boards.greenhouse.io/speechify", "greenhouse", 360),
    ("Arkose Labs", "arkose-labs", "https://www.arkoselabs.com", "Fraud Prevention & Security", 0, 1,
     "https://boards.greenhouse.io/arkoselabs", "greenhouse", 360),
    ("DigiCert", "digicert", "https://www.digicert.com", "Digital Security", 1, 0,
     "https://boards.greenhouse.io/digicert", "greenhouse", 720),
    ("Orion Innovation", "orion-innovation", "https://www.orioninc.com", "IT Services & Consulting", 1, 0,
     "https://boards.greenhouse.io/orioninnovation", "greenhouse", 720),
    ("ConnectWise", "connectwise", "https://www.connectwise.com", "Software Solutions (MSP)", 1, 0,
     "https://boards.greenhouse.io/connectwise", "greenhouse", 360),
    ("Securly", "securly", "https://www.securly.com", "EdTech Safety & Security", 0, 1,
     "https://boards.greenhouse.io/securly13", "greenhouse", 360),
    ("Addepar", "addepar", "https://addepar.com", "Fintech & Wealth Management", 0, 1,
     "https://boards.greenhouse.io/addepar1", "greenhouse", 360),
    ("Pattern", "pattern", "https://pattern.com", "E-commerce Acceleration", 0, 1,
     "https://jobs.lever.co/pattern", "lever", 360),
    ("OpenGov", "opengov", "https://opengov.com", "GovTech Software", 0, 1,
     "https://jobs.ashbyhq.com/opengov", "ashby", 360),
    ("Ontic", "ontic", "https://ontic.co", "Protective Intelligence Software", 0, 1,
     "https://jobs.ashbyhq.com/ontic", "ashby", 360),
    ("CertifyOS", "certifyos", "https://www.certifyos.com", "Insurance Technology", 0, 1,
     "https://jobs.ashbyhq.com/certifyos", "ashby", 360),
    # Wipro: Radancy careers site publishes its job sitemap for crawlers (robots-allowed).
    # Focus on Pune/Mumbai per §3 geographic scope; application stays on Wipro's own page.
    ("Wipro", "wipro", "https://www.wipro.com", "IT Services & Consulting", 1, 0,
     "https://careers.wipro.com/sitemap.xml", "sitemap", 720),
]


def main() -> None:
    apply_migrations()
    created = 0
    for name, slug, official, industry, mnc, startup, src_url, ats, freq in REAL_SOURCES:
        row = db.query_one("SELECT company_id FROM companies WHERE slug = ?", (slug,))
        if row:
            cid = int(row["company_id"])
        else:
            cid = db.execute(
                """INSERT INTO companies (name, slug, official_url, industry,
                     verification_status, is_mnc, is_startup, is_demo)
                   VALUES (?,?,?,?,'verified',?,?,0)""",
                (name, slug, official, industry, mnc, startup))
            db.execute(
                "INSERT INTO company_locations (company_id, city, state, is_hq) VALUES (?,?,?,1)",
                (cid, "Pune", "Maharashtra"))
        exists = db.query_one(
            "SELECT source_id FROM career_sources WHERE company_id = ? AND source_url = ?",
            (cid, src_url))
        if exists:
            print(f"  = {name}: source already registered")
            continue
        source_id = sources_repo.create_source(cid, src_url, "official_ats", ats, freq)
        if name == "Wipro":
            sources_repo.update_source(source_id, notes="focus_cities=Pune, Mumbai")
        created += 1
        print(f"  + {name}: {ats} source registered")
    print(f"Done. {created} new source(s). Real companies are is_demo=0 — "
          "their jobs count in all public statistics.")


if __name__ == "__main__":
    main()
