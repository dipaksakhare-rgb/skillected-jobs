"""Seed clearly-labeled DEMO data (§84).

Every seeded company/job is marked is_demo=1 and renders a DEMO DATA badge; demo rows
are excluded from all public statistics and the Placement Radar. Idempotent: safe to
re-run. Run AFTER scripts/apply_migrations.py.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core import database as db  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.services import scoring  # noqa: E402
from app.services.taxonomy import resolve_skill  # noqa: E402



def _ts(minutes_ago: float) -> str:
    dt = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


COMPANIES = [
    # (name, industry, mnc, startup, careers_url, official_url)
    ("Persistent Systems", "IT Services & Consulting", 1, 0,
     "https://www.persistent.com/careers/", "https://www.persistent.com/"),
    ("KPIT Technologies", "Automotive Software", 1, 0,
     "https://www.kpit.com/careers/", "https://www.kpit.com/"),
    ("Zoho", "Software Products", 1, 0,
     "https://www.zoho.com/careers/", "https://www.zoho.com/"),
    ("Sarvaha Systems", "IT Services", 0, 1,
     "https://www.sarvaha.com/careers", "https://www.sarvaha.com/"),
    ("TechAroma Labs", "Product Startup", 0, 1,
     "https://techaroma.example.com/careers", "https://techaroma.example.com/"),
    ("Wakad Analytics Works", "Analytics Services", 0, 1,
     "https://wakadanalytics.example.com/careers", "https://wakadanalytics.example.com/"),
    ("Deccan Secure Systems", "Cybersecurity Services", 0, 1,
     "https://deccansecure.example.com/careers", "https://deccansecure.example.com/"),
    ("Kothrud Embedded Works", "Embedded & IoT", 0, 1,
     "https://kothrudembedded.example.com/careers", "https://kothrudembedded.example.com/"),
]

SOURCES = [
    # (company_name, source_url, source_type, ats_type, frequency, status, checked_min_ago)
    ("Persistent Systems", "https://www.persistent.com/careers/", "official_careers", "", 720, "healthy", 42),
    ("KPIT Technologies", "https://www.kpit.com/careers/", "official_careers", "", 720, "healthy", 96),
    ("Zoho", "https://www.zoho.com/careers/", "official_careers", "", 720, "delayed", 1500),
    ("Sarvaha Systems", "https://www.sarvaha.com/careers", "official_careers", "", 1440, "healthy", 300),
    ("TechAroma Labs", "https://techaroma.example.com/feed/jobs.xml", "official_careers", "", 60, "error", 500),
    ("Wakad Analytics Works", "https://wakadanalytics.example.com/careers", "official_careers", "", 360, "healthy", 20),
    ("Deccan Secure Systems", "https://deccansecure.example.com/careers", "official_careers", "", 720, "never_checked", None),
    ("Kothrud Embedded Works", "https://kothrudembedded.example.com/careers", "official_careers", "", 720, "never_checked", None),
]

# (company, title, domain_slug, city, work_mode, emp_type, exp_min, exp_max, salary,
#  skills, description, reqs, fresher, posted_min_ago, verified_posting, status)
JOBS = [
    ("Persistent Systems", "Software Engineer — Java", "full-stack", "Pune", "hybrid",
     "full_time", 1, 3, (900000, 1400000),
     ["Java", "Spring Boot", "SQL", "Git"],
     "Join the product engineering team building enterprise platforms for global clients. Work in hybrid mode from our Pune office.",
     ["1–3 years of Java and Spring Boot experience", "Strong SQL and REST API skills", "Good communication"],
     0, 24, 1, "active"),
    ("Persistent Systems", "Senior React Developer", "full-stack", "Pune", "hybrid",
     "full_time", 3, 6, (1600000, 2400000),
     ["React", "TypeScript", "JavaScript", "Node.js"],
     "Frontend-focused role on a modern React + TypeScript stack with design-system ownership.",
     ["3+ years React in production", "TypeScript proficiency", "Experience with component libraries"],
     0, 300, 1, "active"),
    ("KPIT Technologies", "Embedded Software Engineer", "embedded-iot", "Pune", "onsite",
     "full_time", 0, 2, (500000, 800000),
     ["Embedded C", "ARM", "RTOS", "CAN Bus"],
     "Automotive embedded development for global OEM programs. Training provided on AUTOSAR.",
     ["BE/BTech in E&TC, Instrumentation or CS", "C programming fundamentals", "Willingness to work onsite"],
     1, 90, 1, "active"),
    ("KPIT Technologies", "Graduate Engineer Trainee — Automotive", "embedded-iot", "Pune", "onsite",
     "full_time", 0, 0, (400000, 550000),
     ["C", "Microcontrollers", "Python"],
     "12-month structured GET program across embedded software teams; rotational assignments.",
     ["2025/2026 graduate", "60%+ aggregate", "Aptitude for embedded systems"],
     1, 1500, 0, "active"),
    ("Zoho", "Member Technical Staff — Full Stack", "full-stack", "Pune", "onsite",
     "full_time", 0, 3, None,
     ["JavaScript", "Java", "MySQL", "HTML"],
     "Build customer-facing product features end-to-end. Zoho's product-first engineering culture.",
     ["Strong programming fundamentals", "Any stack exposure", "Portfolio or open-source work a plus"],
     1, 1500, 0, "active"),
    ("Sarvaha Systems", "Data Analyst", "data-analytics", "Pune", "onsite",
     "full_time", 0, 2, (450000, 700000),
     ["SQL", "Power BI", "Excel", "Python"],
     "Analytics team serving manufacturing clients: dashboards, reporting automation, ETL checks.",
     ["SQL querying confidence", "Power BI or Tableau basics", "Clear written communication"],
     1, 45, 1, "active"),
    ("Sarvaha Systems", "Business Analyst", "business-analysis", "Pune", "hybrid",
     "full_time", 1, 4, (600000, 1000000),
     ["Requirements Gathering", "User Stories", "Agile", "SQL"],
     "Bridge client stakeholders and delivery teams; own requirement documents and acceptance criteria.",
     ["1–4 years BA or adjacent experience", "Excellent documentation", "Agile exposure"],
     0, 2200, 0, "active"),
    ("TechAroma Labs", "AI/ML Engineer — GenAI", "data-science-ai-ml", "Pune", "remote",
     "full_time", 1, 4, (1200000, 2000000),
     ["Python", "PyTorch", "LLMs", "RAG", "LangChain"],
     "Build retrieval-augmented generation features on top of open models; ship fast, measure everything.",
     ["Hands-on LLM application experience", "Python + PyTorch", "Startup mindset"],
     0, 600, 0, "active"),
    ("Wakad Analytics Works", "Junior Data Scientist", "data-science-ai-ml", "Pune", "hybrid",
     "full_time", 0, 1, (500000, 750000),
     ["Python", "Pandas", "scikit-learn", "SQL"],
     "Entry-level data science on retail analytics engagements with senior mentorship.",
     ["Python + pandas projects", "Statistics fundamentals", "Final-year students may apply"],
     1, 18, 1, "active"),
    ("Wakad Analytics Works", "Power BI Developer", "data-analytics", "Pune", "hybrid",
     "full_time", 1, 3, (550000, 900000),
     ["Power BI", "SQL", "DAX", "Data Visualization"],
     "Own dashboard delivery for logistics clients; DAX modeling and performance tuning.",
     ["1–3 years Power BI", "Advanced SQL", "Stakeholder handling"],
     0, 2600, 0, "active"),
    ("Deccan Secure Systems", "SOC Analyst (L1)", "cybersecurity", "Pune", "onsite",
     "full_time", 0, 2, (450000, 650000),
     ["SIEM", "SOC Operations", "Incident Response", "Wireshark"],
     "24x7 SOC monitoring for enterprise clients; rotation-based shifts; fast escalation paths.",
     ["SIEM familiarity (any product)", "Networking basics (TCP/IP)", "Night-shift readiness"],
     1, 240, 1, "active"),
    ("Deccan Secure Systems", "VAPT Analyst", "cybersecurity", "Pune", "hybrid",
     "full_time", 1, 3, (600000, 1100000),
     ["VAPT", "Burp Suite", "OWASP", "Nmap"],
     "Web/mobile/network penetration testing engagements with structured reporting duties.",
     ["1–3 years VAPT experience", "OWASP Top 10 fluency", "Report writing skills"],
     0, 1300, 0, "active"),
    ("Kothrud Embedded Works", "Firmware Engineer — IoT", "embedded-iot", "Pune", "onsite",
     "full_time", 1, 4, (700000, 1200000),
     ["Embedded C", "MQTT", "STM32", "IoT"],
     "Design firmware for connected industrial devices; own the full bring-up cycle.",
     ["Embedded C on ARM Cortex", "MQTT/protocol experience", "Debugging with JTAG/SWD"],
     0, 2900, 0, "active"),
    ("Kothrud Embedded Works", "QA Automation Engineer", "qa-testing", "Pune", "hybrid",
     "full_time", 0, 2, (450000, 700000),
     ["Selenium", "Python", "API Testing", "Automation Testing"],
     "Automate regression suites for embedded companion web apps; grow into SDET.",
     ["Selenium or Playwright basics", "Python scripting", "Eye for detail"],
     1, 5000, 0, "active"),
    ("TechAroma Labs", "DevOps Intern", "devops-cloud", "Pune", "hybrid",
     "internship", 0, 0, (150000, 240000),
     ["Linux", "Docker", "Git", "AWS"],
     "6-month internship on CI/CD tooling and cloud cost dashboards; conversion possible.",
     ["Linux comfort", "Any cloud exposure", "Final-year or recently graduated"],
     1, 4000, 0, "active"),
    ("Persistent Systems", "Cloud Support Engineer", "devops-cloud", "Pune", "onsite",
     "full_time", 1, 3, (600000, 950000),
     ["AWS", "Linux", "Docker", "Troubleshooting"],
     "Support enterprise cloud workloads; incident triage, runbooks, automation of fixes.",
     ["1–3 years support/ops experience", "AWS services exposure", "Scripting skills"],
     0, 6100, 0, "active"),
    ("Zoho", "QA Engineer — Web", "qa-testing", "Pune", "onsite",
     "full_time", 0, 2, None,
     ["Manual Testing", "API Testing", "SQL"],
     "Own test plans for a web product area; manual + early automation exposure.",
     ["Testing fundamentals", "SQL basics", "Detail orientation"],
     1, 8000, 0, "active"),
    ("Sarvaha Systems", "Backend Developer — Python/Django", "full-stack", "Pune", "hybrid",
     "full_time", 1, 3, (700000, 1100000),
     ["Python", "Django", "PostgreSQL", "REST APIs"],
     "Own backend services for a logistics SaaS; API design and performance work.",
     ["1–3 years Django", "PostgreSQL proficiency", "REST API design"],
     0, 9500, 0, "active"),
    # one expired job to exercise expiry display (§48)
    ("Wakad Analytics Works", "Reporting Analyst (Contract)", "data-analytics", "Pune", "remote",
     "contract", 1, 3, (400000, 600000),
     ["Excel", "SQL", "Reporting"],
     "Six-month contract for report automation. Position filled.",
     ["Excel mastery", "SQL basics"], 0, 12000, 0, "expired"),
]


def seed() -> None:
    # ---- companies --------------------------------------------------------
    company_ids: dict[str, int] = {}
    for name, industry, mnc, startup, careers, official in COMPANIES:
        slug = name.lower().replace(" ", "-").replace(".", "")
        row = db.query_one("SELECT company_id FROM companies WHERE slug = ?", (slug,))
        if row:
            company_ids[name] = int(row["company_id"])
            continue
        cid = db.execute(
            """INSERT INTO companies (name, slug, official_url, careers_url, industry,
                 verification_status, is_mnc, is_startup, is_demo)
               VALUES (?,?,?,?,?,'verified',?,?,1)""",
            (name, slug, official, careers, industry, mnc, startup),
        )
        company_ids[name] = cid
        db.execute(
            "INSERT INTO company_locations (company_id, city, state, is_hq) VALUES (?,?,?,1)",
            (cid, "Pune", "Maharashtra"),
        )

    # ---- sources ----------------------------------------------------------
    for name, url, stype, ats, freq, status, checked in SOURCES:
        cid = company_ids[name]
        exists = db.query_one(
            "SELECT source_id FROM career_sources WHERE company_id=? AND source_url=?", (cid, url))
        if exists:
            continue
        db.execute(
            """INSERT INTO career_sources (company_id, source_url, source_type, ats_type,
                 crawl_frequency_minutes, active, last_checked_at, status, error_count, reliability_score)
               VALUES (?,?,?,?,?,1,?,?,?,?)""",
            (cid, url, stype, ats, freq,
             _ts(checked) if checked is not None else None,
             status, 2 if status == "error" else 0,
             95.0 if stype == "official_careers" else 85.0),
        )

    # ---- jobs -------------------------------------------------------------
    domain_rows = {r["slug"]: int(r["domain_id"]) for r in
                   db.query_all("SELECT domain_id, slug FROM domains")}
    seeded = 0
    for (company, title, dslug, city, wmode, etype, emin, emax, salary, skills,
         desc, reqs, fresher, mins_ago, verified_posting, status) in JOBS:
        cid = company_ids[company]
        slug = title.lower().replace(" ", "-").replace("/", "-").replace("—", "-")
        slug = "".join(ch for ch in slug if ch.isalnum() or ch == "-")[:60].strip("-")
        dhash = scoring.duplicate_hash(company, title, city, None,
                                       f"https://demo.invalid/apply/{slug}")
        if db.query_one("SELECT job_id FROM jobs WHERE duplicate_hash = ?", (dhash,)):
            continue
        salary_min, salary_max = salary if salary else (None, None)
        published = _ts(mins_ago)
        verified_at = _ts(min(mins_ago, 45))
        jid = db.execute(
            """INSERT INTO jobs (company_id, company_name, job_title, normalized_job_title, slug,
                 domain_id, location, city, state, work_mode, employment_type,
                 experience_min, experience_max, education, skills, technologies,
                 salary_min, salary_max, salary_currency, job_description, requirements,
                 source_type, source_url, application_url, official_company_url,
                 posting_date, posting_date_verified, first_seen_at, last_verified_at,
                 job_status, verification_status, verification_score, authenticity_score,
                 duplicate_hash, is_fresher_friendly, is_demo, published_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)""",
            (cid, company, title, title.lower(), slug,
             domain_rows.get(dslug), "Pune, Maharashtra", city, "Maharashtra", wmode, etype,
             emin, emax, "Not specified", json.dumps(skills), json.dumps(skills),
             salary_min, salary_max, "INR", desc, json.dumps(reqs),
             "official_careers", f"https://demo.invalid/careers/{slug}",
             f"https://demo.invalid/apply/{slug}", "https://demo.invalid/",
             published if verified_posting else None, verified_posting,
             published, verified_at,
             status, "approved", 92.0, 96.0,
             dhash, fresher, published),
        )
        for skill in skills:
            sid = resolve_skill(skill)
            if sid:
                db.execute(
                    "INSERT OR IGNORE INTO job_skills (job_id, skill_id, is_required) VALUES (?,?,1)",
                    (jid, sid),
                )
        db.execute(
            """INSERT INTO events (event_type, entity_type, entity_id, payload)
               VALUES ('JOB_PUBLISHED','job',?,?)""",
            (jid, json.dumps({"company": company, "title": title})),
        )
        seeded += 1

    # ---- Skillected course catalog (§37 — official site as source of truth) ----
    from app.repositories import courses_repo
    courses_repo.ensure_courses()

    # ---- admin user (bootstrap, not demo-labeled) --------------------------
    # Credentials come from env (ADMIN_EMAIL / ADMIN_PASSWORD) so production
    # never inherits the development defaults.
    import os
    admin_email = os.getenv("ADMIN_EMAIL", "admin@skillected.local")
    admin_password = os.getenv("ADMIN_PASSWORD", "ChangeMe!Admin1")
    if not db.query_one("SELECT user_id FROM users WHERE email = ?", (admin_email,)):
        uid = db.execute(
            "INSERT INTO users (email, password_hash, full_name) VALUES (?,?,?)",
            (admin_email, hash_password(admin_password), "Platform Admin"),
        )
        db.execute(
            """INSERT INTO user_roles (user_id, role_id)
               SELECT ?, role_id FROM roles WHERE name = 'admin'""", (uid,),
        )
        po = db.execute(
            "INSERT INTO users (email, password_hash, full_name) VALUES (?,?,?)",
            (os.getenv("PLACEMENT_EMAIL", "placement@skillected.local"),
             hash_password(os.getenv("PLACEMENT_PASSWORD", "ChangeMe!Officer1")),
             "Placement Officer"),
        )
        db.execute(
            """INSERT INTO user_roles (user_id, role_id)
               SELECT ?, role_id FROM roles WHERE name = 'placement_officer'""", (po,),
        )

    print(f"Seed complete: {seeded} demo job(s), {len(COMPANIES)} companies, "
          f"{len(SOURCES)} sources. All demo rows are labeled is_demo=1.")


if __name__ == "__main__":
    seed()
