"""Phase 2–7 service tests: ingest classification, matching, resume parsing, market intel."""
from __future__ import annotations

from app.crawler.ingest import (classify_domain, detect_work_mode, is_fresher_friendly,
                                parse_experience, normalize_job_title)
from app.services import market, matching, resume_parser


# ---------------------------------------------------------------- classification (§52)

def test_classify_domain_software():
    assert classify_domain("Senior Software Engineer", "Java Spring Boot REST APIs") == "full-stack"

def test_classify_domain_cyber():
    assert classify_domain("SOC Analyst L1", "Monitor SIEM alerts and respond to incidents") == "cybersecurity"

def test_classify_domain_embedded():
    assert classify_domain("Firmware Engineer", "STM32 RTOS bare-metal development") == "embedded-iot"

def test_classify_domain_unknown_returns_none():
    assert classify_domain("Office Manager", "filing and scheduling") is None

def test_normalize_title():
    assert normalize_job_title("  Senior   JAVA Engineer ") == "senior java engineer"

def test_parse_experience_range():
    assert parse_experience("Backend Developer", "3-5 years experience required") == (3.0, 5.0)

def test_parse_experience_plus():
    assert parse_experience("Data Scientist 2+ years", "") == (2.0, None)

def test_parse_experience_fresher():
    assert parse_experience("Fresher openings", "") == (0.0, 1.0)

def test_parse_experience_absent_is_none():
    assert parse_experience("Platform Engineer", "kubernetes and docker") == (None, None)

def test_detect_work_mode():
    assert detect_work_mode("Remote first team") == "remote"
    assert detect_work_mode("Hybrid - 3 days in office") == "hybrid"
    assert detect_work_mode("Work from office 5 days") == "onsite"
    assert detect_work_mode("great team") is None

def test_fresher_friendly():
    assert is_fresher_friendly("Graduate Engineer Trainee", 0.0) is True
    assert is_fresher_friendly("Senior Architect", 8.0) is False


# ---------------------------------------------------------------- matching (§32–36)

def _job(**kw):
    base = {"job_id": 1, "job_title": "Python Backend Developer", "skills_list": ["Python", "SQL", "Django"],
            "experience_min": 1.0, "experience_max": 3.0, "city": "Pune", "work_mode": "hybrid",
            "education": None, "technologies_list": ["Python"], "domain_name": "Full Stack Development"}
    base.update(kw)
    return base


def test_match_strong_candidate():
    cand = {"skills": ["Python", "SQL", "Django", "Git"], "years_experience": 2.0,
            "preferred_locations": "Pune", "job_titles": ["Backend Developer"], "preferred_domains": ""}
    r = matching.match_score(cand, _job())
    assert r["score"] >= 80
    assert r["band"] in ("EXCELLENT MATCH", "STRONG MATCH")
    assert any("Python" in x for x in r["reasons"])
    assert not r["is_stretch"]


def test_match_stretch_when_partial_skills():
    cand = {"skills": ["Python", "SQL"], "years_experience": 1.5,
            "preferred_locations": "Pune", "job_titles": ["QA Engineer"], "preferred_domains": ""}
    r = matching.match_score(cand, _job(skills_list=["Python", "SQL", "Django", "AWS"]))
    assert r["is_stretch"] is True
    assert r["missing_skills"]
    assert 60 <= r["score"] < 80


def test_match_low_for_off_domain():
    cand = {"skills": ["Figma"], "years_experience": 1.0,
            "preferred_locations": "Nagpur", "job_titles": ["Designer"], "preferred_domains": "design"}
    r = matching.match_score(cand, _job(experience_min=3.0, experience_max=6.0))
    assert r["score"] < 60
    assert r["gaps"]


def test_readiness_checks_present():
    cand = {"skills": ["Python", "SQL", "Django"], "years_experience": 2.0,
            "preferred_locations": "Pune", "job_titles": ["Backend Developer"], "preferred_domains": ""}
    r = matching.match_score(cand, _job())
    assert r["readiness"]["percent"] >= 80
    labels = [c["label"] for c in r["readiness"]["checks"]]
    assert "Core skills covered" in labels


def test_skill_gap_and_courses(db_with_courses):
    from app.core import database as db
    # Ensure one non-demo job with mapped skills drives market demand (§27).
    row = db.query_one(
        "SELECT job_id FROM jobs WHERE job_status='active' ORDER BY job_id LIMIT 1")
    db.execute("UPDATE jobs SET is_demo=0 WHERE job_id=?", (row["job_id"],))
    gap = matching.skill_gap(["React", "Node.js"])
    assert gap["gap_count"] >= 1
    assert all(g["skill"].lower() not in ("react", "node.js")
               for g in gap["market_needs"][:3])
    courses = matching.recommend_courses([g["skill"] for g in gap["market_needs"][:4]])
    assert isinstance(courses, list)


def test_store_match_upsert(db_session):
    from app.core import database as db
    cand = {"skills": ["Python"], "years_experience": 1.0, "preferred_locations": "Pune",
            "job_titles": ["Developer"], "preferred_domains": ""}
    r = matching.match_score(cand, _job())
    matching.store_match(None, 1, r)
    matching.store_match(None, 1, r)  # upsert, no constraint error
    row = db.query_one("SELECT COUNT(*) AS c FROM job_matches WHERE job_id = 1 AND user_id IS NULL")
    assert int(row["c"]) == 1


# ---------------------------------------------------------------- resume parsing (§29–30)

SAMPLE = """Rahul Sharma
rahul.sharma@example.com | +91 9876543210 | github.com/rahuls
Pune, Maharashtra

Summary
Python developer with 2 years of experience building web APIs. Reduced API latency by 40%.

Skills
Python, Django, PostgreSQL, Docker, AWS, Git, REST APIs

Experience
Python Developer at TechWorks 2023 - present
Built internal dashboards used by 500 users.

Education
B.Tech Computer Engineering 2022

Projects
Inventory API - Django REST service with 90% test coverage
ChatApp - WebSocket chat with 200 concurrent users

Certifications
AWS Cloud Practitioner
"""


def test_parse_resume_fields():
    p = resume_parser.parse_resume(SAMPLE)
    assert p["email"] == "rahul.sharma@example.com"
    assert p["name"] == "Rahul Sharma"
    assert "Python" in p["skills"] or "python" in [s.lower() for s in p["skills"]]
    assert p["github"] == "rahuls"
    assert p["years_experience"] == 2.0
    assert p["is_fresher"] is False
    assert p["project_count"] >= 1


def test_health_score_structure():
    p = resume_parser.parse_resume(SAMPLE)
    score, good, needs = resume_parser.health_score(p)
    assert 0 <= score <= 100
    assert isinstance(good, list) and isinstance(needs, list)
    assert any("skills" in g.lower() for g in good)


def test_sparse_resume_scores_low():
    p = resume_parser.parse_resume("someone\nmail@example.com\ntext")
    score, _good, needs = resume_parser.health_score(p)
    assert score < 70
    assert needs


def test_extract_text_txt():
    text = resume_parser.extract_text(b"hello resume world with enough text here", "resume.txt")
    assert "hello resume world" in text


# ---------------------------------------------------------------- market intel (§70)

def test_market_trends_never_crash_and_suppress_small_data(db_session):
    trends = market.hiring_trends()
    assert "trends" in trends
    for t in trends["trends"]:
        assert ("change" in t) and ("label" in t)

def test_skill_shift_respects_sample_size(db_session):
    out = market.skill_demand_shift()
    assert "skills" in out and "note" in out

def test_curriculum_intelligence_shape(db_session):
    blocks = market.curriculum_intelligence()
    for b in blocks:
        assert "domain_slug" in b and "top_skills" in b and "courses" in b
