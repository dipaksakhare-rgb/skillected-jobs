"""Resume parsing (§29–30) — deterministic extraction, no AI required.

Supported: PDF (pypdf), DOCX (python-docx), TXT. Produces a structured profile
with None for unknown fields (§55 — never invent). AI providers can be layered
later via AI_PROVIDER without changing this interface (§106).
"""
from __future__ import annotations

import json
import re

from app.core import database as db

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE_RE = re.compile(r"(?:\+91[\s-]?)?[6-9]\d{9}")
GITHUB_RE = re.compile(r"(?:github\.com/)([\w-]+)", re.I)
LINKEDIN_RE = re.compile(r"(?:linkedin\.com/in/)([\w-]+)", re.I)

SECTION_HEADS = {
    "summary": ("summary", "profile", "objective", "about"),
    "skills": ("skills", "technical skills", "technologies", "tech stack"),
    "experience": ("experience", "work experience", "professional experience", "employment"),
    "education": ("education", "academics", "qualifications"),
    "projects": ("projects", "academic projects", "personal projects"),
    "certifications": ("certifications", "certificates", "licenses"),
}

SKILL_HINTS = [
    "python", "java", "javascript", "typescript", "c++", "c#", "sql", "nosql", "html", "css",
    "react", "angular", "vue", "node.js", "nodejs", "django", "flask", "spring boot", "fastapi",
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "jenkins", "git", "github",
    "linux", "mysql", "postgresql", "postgres", "mongodb", "redis", "oracle",
    "power bi", "powerbi", "tableau", "excel", "pandas", "numpy", "scikit-learn", "sklearn",
    "tensorflow", "pytorch", "keras", "opencv", "nlp", "llm", "machine learning", "deep learning",
    "selenium", "playwright", "cypress", "api testing", "manual testing", "automation",
    "embedded c", "arm", "stm32", "rtos", "mqtt", "iot", "siem", "vapt", "burp suite", "nmap",
    "wireshark", "penetration testing", "rest api", "graphql", "microservices", "gitlab",
    "agile", "scrum", "jira", "sap", "salesforce", "servicenow", "rpa", "power bi dax",
]

DEGREE_TOKENS = ["b.e", "be", "b.tech", "btech", "b tech", "m.tech", "mtech", "bsc", "m.sc",
                 "msc", "bca", "mca", "bcom", "mcom", "mba", "diploma", "phd", "12th", "10th"]

FRESHER_TOKENS = re.compile(r"\b(fresher|intern|trainee|graduate)\b", re.I)


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract text from PDF/DOCX/TXT bytes."""
    lower = (filename or "").lower()
    if lower.endswith(".pdf"):
        from pypdf import PdfReader
        import io
        reader = PdfReader(io.BytesIO(file_bytes))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    if lower.endswith((".docx",)):
        import docx  # python-docx
        import io
        document = docx.Document(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in document.paragraphs)
    return file_bytes.decode("utf-8", errors="replace")


def _section_bounds(text: str) -> dict[str, tuple[int, int]]:
    lines = [l.strip() for l in text.splitlines()]
    heads: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        low = line.lower().rstrip(": ")
        if low in SECTION_HEADS or any(low == h or (len(low) < 40 and low == h)
                                       for heads_list in SECTION_HEADS.values() for h in heads_list):
            for key, aliases in SECTION_HEADS.items():
                if low in aliases:
                    heads.append((i, key))
                    break
    bounds: dict[str, tuple[int, int]] = {}
    for idx, (i, key) in enumerate(heads):
        end = heads[idx + 1][0] if idx + 1 < len(heads) else len(lines)
        bounds.setdefault(key, (i + 1, end))
    return bounds


def _section_text(text: str, key: str) -> str:
    bounds = _section_bounds(text)
    if key not in bounds:
        return ""
    lines = text.splitlines()
    start, end = bounds[key]
    return "\n".join(lines[start:end]).strip()


def parse_years_experience(text: str) -> float | None:
    """Total years: explicit 'X years' claims first, then date-range arithmetic."""
    m = re.search(r"(\d{1,2}(?:\.\d)?)\s*\+?\s*years?\s+(?:of\s+)?(?:total\s+)?experience", text, re.I)
    if m:
        return float(m.group(1))
    years = set()
    for m in re.finditer(r"\b(20\d{2})\s*(?:-|–|to)\s*(20\d{2}|present|current|till date)\b", text, re.I):
        start = int(m.group(1))
        end_raw = m.group(2).lower()
        end = 2026 if any(t in end_raw for t in ("present", "current", "till")) else int(end_raw)
        if 2000 <= start <= end <= 2030:
            years.add((start, end))
    if not years:
        return None
    spans = sorted(years)
    total = 0.0
    cur_s, cur_e = spans[0]
    for s, e in spans[1:]:
        if s <= cur_e:
            cur_e = max(cur_e, e)
        else:
            total += cur_e - cur_s
            cur_s, cur_e = s, e
    total += cur_e - cur_s
    return round(min(total, 40.0), 1)


def parse_resume(text: str) -> dict:
    """Structured profile — unknown → None/[] (§55)."""
    email = EMAIL_RE.search(text)
    phone = PHONE_RE.search(text)
    github = GITHUB_RE.search(text)
    linkedin = LINKEDIN_RE.search(text)

    name = None
    for line in text.splitlines()[:6]:
        clean = line.strip()
        if (2 <= len(clean.split()) <= 4 and clean.istitle()
                and "@" not in clean and not any(ch.isdigit() for ch in clean)):
            name = clean
            break

    skills_raw = _section_text(text, "skills") or ""
    if not skills_raw:
        skills_raw = text
    found_skills: list[str] = []
    low = skills_raw.lower()
    for hint in SKILL_HINTS:
        pattern = r"\b" + re.escape(hint) + r"\b"
        if re.search(pattern, low) and hint not in found_skills:
            found_skills.append(hint.title() if len(hint) > 3 else hint.upper())
    found_skills = found_skills[:25]

    degrees = []
    low_all = text.lower()
    for deg in DEGREE_TOKENS:
        if re.search(r"\b" + re.escape(deg) + r"\b", low_all) and deg not in degrees:
            degrees.append(deg.upper())
    years = parse_years_experience(text)
    projects = _section_text(text, "projects")
    project_titles = []
    for line in projects.splitlines():
        line = line.strip().lstrip("•-*– ")
        if 5 < len(line) < 80 and not line.lower().startswith(("technologies", "skills")):
            project_titles.append(line)
    project_titles = project_titles[:8]

    return {
        "name": name,
        "email": email.group(0) if email else None,
        "phone": phone.group(0) if phone else None,
        "github": github.group(1) if github else None,
        "linkedin": linkedin.group(1) if linkedin else None,
        "summary": _section_text(text, "summary")[:600] or None,
        "skills": found_skills,
        "education": degrees[:6] or None,
        "years_experience": years,
        "is_fresher": bool(years is None or years < 0.5 or FRESHER_TOKENS.search(text[:1500])),
        "project_count": len(project_titles),
        "projects": project_titles,
        "certifications": _section_text(text, "certifications")[:400] or None,
    }


def health_score(profile: dict) -> tuple[float, list[str], list[str]]:
    """§30 resume health — only supported judgments, actionable suggestions."""
    score = 40.0
    good: list[str] = []
    needs: list[str] = []

    if profile.get("skills"):
        n = len(profile["skills"])
        if n >= 8:
            score += 18
            good.append(f"✓ Strong technical skills section ({n} skills)")
        elif n >= 4:
            score += 12
            good.append(f"✓ Technical skills present ({n} skills)")
        else:
            score += 5
            needs.append("⚠ Add more technical skills (aim for 8+)")
    else:
        needs.append("⚠ No technical skills detected — add a Skills section")

    if profile.get("project_count"):
        if profile["project_count"] >= 2:
            score += 14
            good.append(f"✓ {profile['project_count']} projects listed")
        else:
            score += 7
            good.append("✓ Project listed")
    else:
        needs.append("⚠ Add 2–3 projects with technologies used")

    if profile.get("education"):
        score += 8
        good.append("✓ Education listed")

    if profile.get("summary") and len(profile["summary"]) > 80:
        score += 10
        good.append("✓ Professional summary present")
    else:
        needs.append("⚠ Weak or missing professional summary (3–4 lines)")

    if profile.get("years_experience"):
        score += 6
        good.append(f"✓ Experience: {profile['years_experience']} years")

    if profile.get("github"):
        score += 6
        good.append("✓ GitHub profile linked")
    else:
        needs.append("⚠ Add GitHub/portfolio link where relevant")

    measurable = re.search(r"\b\d+\s*%|\b\d+x\b|₹|\$\d|usrs\b|users\b|reduced|improved", 
                           (profile.get("summary") or "") + " " + " ".join(profile.get("projects") or []),
                           re.I)
    if measurable:
        score += 8
        good.append("✓ Measurable achievements detected")
    else:
        needs.append("⚠ Add measurable achievements (%, users, time saved)")

    return round(min(max(score, 0), 100), 1), good, needs


def store_resume(user_id: int, filename: str, file_type: str, parsed: dict,
                 health: float, storage_path: str | None, consent: bool) -> int:
    from app.services import scoring
    resume_id = db.execute(
        """INSERT INTO resumes (user_id, file_name, storage_path, file_type, parse_status,
             parsed_json, health_score, is_active, consent)
           VALUES (?,?,?,?,?,'parsed',?,?,?)""",
        (user_id, filename, storage_path, file_type,
         json.dumps(parsed, default=str), health, 1, 1 if consent else 0),
    )
    # canonical skill links
    from app.services.taxonomy import resolve_skill
    for skill in parsed.get("skills", []):
        sid = resolve_skill(skill)
        if sid:
            db.execute(
                """INSERT OR IGNORE INTO resume_skills (resume_id, skill_id, skill_name, is_core)
                   VALUES (?,?,?,0)""", (resume_id, sid, skill))
    return resume_id
