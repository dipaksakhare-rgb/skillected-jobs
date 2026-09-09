"""Courses repository (§37) — Skillected course catalog + recommendations."""
from __future__ import annotations

from app.core import database as db

# Seeded from the official Skillected website catalog (source of truth, §37).
# official_url points to the live site; fees/details are NEVER stored here.
DEFAULT_COURSES: list[dict] = [
    {"title": "Full Stack Development", "slug": "full-stack-development",
     "domain": "full-stack", "skills": ["JavaScript", "React", "Node.js", "MongoDB", "HTML", "CSS"],
     "description": "Industry-aligned full stack program covering frontend, backend and databases."},
    {"title": "Java Full Stack Development", "slug": "java-full-stack-development",
     "domain": "full-stack", "skills": ["Java", "Spring Boot", "SQL", "REST APIs", "Git"],
     "description": "Java-first full stack track with Spring Boot and enterprise practices."},
    {"title": "Data Science", "slug": "data-science",
     "domain": "data-science-ai-ml", "skills": ["Python", "Pandas", "scikit-learn", "Machine Learning", "Statistics"],
     "description": "Data science program: Python analytics, ML fundamentals and capstone projects."},
    {"title": "Cybersecurity", "slug": "cybersecurity",
     "domain": "cybersecurity", "skills": ["SIEM", "VAPT", "Burp Suite", "Incident Response", "Network Security"],
     "description": "SOC and VAPT-focused cybersecurity training with hands-on labs."},
    {"title": "DevOps & Cloud (AWS)", "slug": "devops-cloud-aws",
     "domain": "devops-cloud", "skills": ["AWS", "Docker", "Kubernetes", "Terraform", "Jenkins", "CI/CD"],
     "description": "DevOps engineering track: containers, IaC and cloud operations."},
    {"title": "Data Analytics", "slug": "data-analytics",
     "domain": "data-analytics", "skills": ["SQL", "Power BI", "Excel", "Data Visualization"],
     "description": "Analytics program: SQL, BI dashboards and reporting workflows."},
    {"title": "Business Analyst", "slug": "business-analyst",
     "domain": "business-analysis", "skills": ["Requirements Gathering", "User Stories", "Agile", "SQL"],
     "description": "BA program: requirement engineering, documentation and agile delivery."},
    {"title": "Embedded Systems", "slug": "embedded-systems",
     "domain": "embedded-iot", "skills": ["Embedded C", "ARM", "RTOS", "Microcontrollers", "IoT"],
     "description": "Embedded track: C programming, microcontrollers and IoT protocols."},
]


def ensure_courses() -> None:
    """Idempotent seed of the Skillected catalog (no fees stored — §37)."""
    domain_ids = {r["slug"]: int(r["domain_id"]) for r in
                  db.query_all("SELECT domain_id, slug FROM domains")}
    for course in DEFAULT_COURSES:
        row = db.query_one("SELECT course_id FROM courses WHERE slug = ?", (course["slug"],))
        if row:
            cid = int(row["course_id"])
        else:
            cid = db.execute(
                """INSERT INTO courses (title, slug, domain_id, official_url, description, is_active,
                     last_synced_at) VALUES (?,?,?,?,?,1,datetime('now'))""",
                (course["title"], course["slug"], domain_ids.get(course["domain"]),
                 "https://www.skillected.com/", course["description"]),
            )
        from app.services.taxonomy import resolve_skill
        for skill in course["skills"]:
            sid = resolve_skill(skill)
            if sid:
                db.execute(
                    "INSERT OR IGNORE INTO course_skills (course_id, skill_id) VALUES (?,?)",
                    (cid, sid))


def list_courses() -> list[dict]:
    rows = db.query_all(
        """SELECT c.*, d.name AS domain_name, d.slug AS domain_slug,
             (SELECT GROUP_CONCAT(st.canonical, ', ') FROM course_skills cs
                JOIN skill_taxonomy st ON st.skill_id = cs.skill_id
                WHERE cs.course_id = c.course_id) AS skills
           FROM courses c LEFT JOIN domains d ON d.domain_id = c.domain_id
           WHERE c.is_active = 1 ORDER BY c.title""")
    return [dict(r) for r in rows]


def courses_for_domain(domain_slug: str) -> list[dict]:
    return [c for c in list_courses() if c.get("domain_slug") == domain_slug]
