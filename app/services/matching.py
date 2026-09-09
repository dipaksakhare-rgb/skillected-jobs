"""Candidate ↔ job matching (§32–36, §38).

Weighted deterministic core (§32 weights) + semantic role equivalence (§35) via
the search service synonyms. AI providers may refine parsing later, but scoring
stays deterministic and explainable (§56). Every score ships with a reason list —
never a bare percentage (§33).
"""
from __future__ import annotations

import json

from app.core import database as db
from app.services.search import expand_role

WEIGHTS = {
    "skills": 0.35,
    "experience": 0.20,
    "title": 0.15,
    "education": 0.10,
    "location": 0.10,
    "tech_stack": 0.05,
    "domain": 0.05,
}

MATCH_BANDS = [(90, "EXCELLENT MATCH"), (80, "STRONG MATCH"), (70, "GOOD MATCH"),
               (60, "POSSIBLE MATCH"), (0, "LOW MATCH")]


def band_for(score: float) -> str:
    for floor, label in MATCH_BANDS:
        if score >= floor:
            return label
    return "LOW MATCH"


def _tokens(values: list[str] | None) -> set[str]:
    out: set[str] = set()
    for v in values or []:
        out.update(t.strip().lower() for t in str(v).replace(",", " ").split() if t.strip())
    return out


def _skill_overlap(cand_skills: list[str], job_skills: list[str]) -> tuple[list[str], list[str]]:
    """(matched, missing) using canonical-ish case-insensitive comparison."""
    def norm(s: str) -> str:
        return s.strip().lower().replace("reactjs", "react").replace("nodejs", "node.js")

    cset = {norm(s) for s in cand_skills or []}
    matched, missing = [], []
    for s in job_skills or []:
        (matched if norm(s) in cset else missing).append(s)
    return matched, missing


def _title_similarity(cand_titles: list[str], job_title: str) -> float:
    """Title similarity with §35 semantic expansion."""
    jt = job_title.lower()
    expansions = set(expand_role(job_title)) | {job_title.lower()}
    best = 0.0
    for ct in cand_titles or []:
        ctl = ct.lower()
        if ctl and (ctl in jt or jt in ctl):
            best = max(best, 1.0)
            continue
        ct_words = _tokens([ct])
        overlap = sum(1 for w in ct_words if w in jt or any(w in e for e in expansions))
        if ct_words:
            best = max(best, min(1.0, overlap / max(1, len(ct_words))))
    return best


def match_score(candidate: dict, job: dict) -> dict:
    """Score one candidate profile against one job dict; returns full explanation."""
    reasons: list[str] = []
    gaps: list[str] = []

    job_skills = job.get("skills_list") or []
    matched, missing = _skill_overlap(candidate.get("skills") or [], job_skills)
    skill_ratio = (len(matched) / len(job_skills)) if job_skills else 0.5
    skills_pts = skill_ratio * 100
    if matched:
        reasons.append(f"✓ {', '.join(matched[:5])}")
    if missing:
        gaps.extend(f"△ {s}" for s in missing[:5])

    # experience (§20 bands)
    c_exp = candidate.get("years_experience") or 0.0
    j_min = job.get("experience_min")
    j_max = job.get("experience_max")
    if j_min is None and j_max is None:
        exp_ratio, exp_ok = 0.6, True
        reasons.append("✓ No strict experience requirement stated")
    else:
        lo = j_min if j_min is not None else 0.0
        hi = j_max if j_max is not None else lo + 2
        if lo - 0.6 <= c_exp <= hi + 0.6:
            exp_ratio, exp_ok = 1.0, True
            reasons.append(f"✓ {c_exp:g} year(s) experience fits {lo:g}–{hi:g} band")
        elif c_exp < lo:
            exp_ratio, exp_ok = max(0.25, 1 - (lo - c_exp) / 2), True
            gaps.append(f"△ needs {lo:g}+ years (you: {c_exp:g})")
        else:
            exp_ratio, exp_ok = max(0.35, 1 - (c_exp - hi) / 3), True
            gaps.append(f"△ role targets up to {hi:g} years (you: {c_exp:g})")

    title_pts = _title_similarity(candidate.get("job_titles") or [candidate.get("headline") or ""],
                                  job.get("job_title") or "") * 100

    edu_ok = not (job.get("education") and str(job.get("education")).lower() not in
                  ("not specified", "any", "graduate"))
    edu_pts = 100 if edu_ok else 60
    if edu_ok:
        reasons.append("✓ Education eligible")

    # location (§3)
    c_loc = (candidate.get("preferred_locations") or "").lower()
    job_city = (job.get("city") or "").lower()
    if not c_loc or job_city in c_loc or "pune" in c_loc or "remote" in c_loc:
        loc_pts = 100 if job_city else 70
        if job_city:
            reasons.append(f"✓ {job.get('city')} matches your location preference")
    elif (job.get("work_mode") or "") == "remote":
        loc_pts = 90
        reasons.append("✓ Remote role")
    else:
        loc_pts = 40
        gaps.append(f"△ located in {job.get('city')}")

    tech = set(_tokens(job.get("technologies_list"))) if job.get("technologies_list") else set()
    ctech = _tokens(candidate.get("skills") or [])
    tech_pts = (len(tech & ctech) / len(tech) * 100) if tech else 70

    domain_pts = 100 if (candidate.get("preferred_domains") or "").lower() in \
        f"{(job.get('domain_name') or '').lower()} {job.get('sub_domain') or ''}" else 60

    total = (skills_pts * WEIGHTS["skills"] + exp_ratio * 100 * WEIGHTS["experience"]
             + title_pts * WEIGHTS["title"] + edu_pts * WEIGHTS["education"]
             + loc_pts * WEIGHTS["location"] + tech_pts * WEIGHTS["tech_stack"]
             + domain_pts * WEIGHTS["domain"])

    is_stretch = 60 <= total < 80 and skill_ratio >= 0.5
    readiness = _readiness(exp_ok, edu_ok, loc_pts >= 60, skill_ratio)

    return {
        "score": round(min(max(total, 0), 100), 1),
        "band": band_for(total),
        "reasons": reasons,
        "gaps": gaps,
        "is_stretch": is_stretch,
        "readiness": readiness,
        "matched_skills": matched,
        "missing_skills": missing,
        "components": {"skills": round(skills_pts, 1), "experience": round(exp_ratio * 100, 1),
                       "title": round(title_pts, 1), "education": edu_pts,
                       "location": loc_pts, "tech_stack": round(tech_pts, 1),
                       "domain": domain_pts},
    }


def _readiness(exp_ok: bool, edu_ok: bool, loc_ok: bool, skill_ratio: float) -> dict:
    checks = [("Resume matches role", skill_ratio >= 0.5),
              ("Experience eligible", exp_ok),
              ("Location eligible", loc_ok),
              ("Education eligible", edu_ok),
              ("Core skills covered", skill_ratio >= 0.75)]
    pct = round(sum(20 for _, ok in checks if ok))
    return {"percent": pct, "checks": [{"label": lbl, "ok": bool(ok)} for lbl, ok in checks]}


# ---------------------------------------------------------------- skill gap (§36–37)

def skill_gap(candidate_skills: list[str], domain_slug: str | None = None,
              limit: int = 12) -> dict:
    """Compare candidate skills vs real market demand (real rows only, §27)."""
    from app.repositories import stats_repo
    demand = stats_repo.skill_demand(limit=30, domain_slug=domain_slug)
    have = {s.strip().lower() for s in candidate_skills or []}
    missing = [{"skill": d["canonical"], "demand": d["demand"]}
               for d in demand if d["canonical"].lower() not in have]
    top_have = [s for s in candidate_skills or []
                if s.strip().lower() in {d["canonical"].lower() for d in demand}]
    return {"you_have": top_have, "market_needs": missing[:limit],
            "gap_count": len(missing)}


def recommend_courses(gap_skills: list[str], limit: int = 3) -> list[dict]:
    """§37 — connect skill gaps to Skillected courses via course_skills links."""
    if not gap_skills:
        return []
    marks = ",".join("?" for _ in gap_skills)
    rows = db.query_all(
        f"""SELECT c.course_id, c.title, c.slug, c.official_url, c.description,
              COUNT(cs.skill_id) AS overlap,
              GROUP_CONCAT(st.canonical, ', ') AS covers
            FROM courses c
            JOIN course_skills cs ON cs.course_id = c.course_id
            JOIN skill_taxonomy st ON st.skill_id = cs.skill_id
            WHERE LOWER(st.canonical) IN ({marks})
              AND c.is_active = 1
            GROUP BY c.course_id ORDER BY overlap DESC LIMIT ?""",
        tuple(s.strip().lower() for s in gap_skills) + (limit,),
    )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------- persistence (§38)

def store_match(user_id: int | None, job_id: int, result: dict) -> None:
    if user_id is None:
        # UNIQUE(job_id, user_id) never collides on NULL in SQLite — replace explicitly.
        db.execute("DELETE FROM job_matches WHERE job_id = ? AND user_id IS NULL", (job_id,))
        db.execute(
            """INSERT INTO job_matches (job_id, user_id, job_match_score, candidate_match_score,
                 skill_match_score, experience_match_score, location_match_score,
                 education_match_score, explanation, is_stretch)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (job_id, None, result["score"], result["score"],
             result["components"]["skills"], result["components"]["experience"],
             result["components"]["location"], result["components"]["education"],
             json.dumps({"reasons": result["reasons"], "gaps": result["gaps"],
                         "band": result["band"]}),
             1 if result["is_stretch"] else 0))
        return
    db.execute(
        """INSERT INTO job_matches (job_id, user_id, job_match_score, candidate_match_score,
             skill_match_score, experience_match_score, location_match_score,
             education_match_score, explanation, is_stretch)
           VALUES (?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(job_id, user_id) DO UPDATE SET
             job_match_score=excluded.job_match_score,
             candidate_match_score=excluded.candidate_match_score,
             skill_match_score=excluded.skill_match_score,
             experience_match_score=excluded.experience_match_score,
             location_match_score=excluded.location_match_score,
             education_match_score=excluded.education_match_score,
             explanation=excluded.explanation,
             is_stretch=excluded.is_stretch""",
        (job_id, user_id, result["score"], result["score"],
         result["components"]["skills"], result["components"]["experience"],
         result["components"]["location"], result["components"]["education"],
         json.dumps({"reasons": result["reasons"], "gaps": result["gaps"],
                     "band": result["band"]}),
         1 if result["is_stretch"] else 0),
    )


def jobs_for_candidate(candidate: dict, user_id: int | None = None,
                       limit: int = 20, min_score: float = 55.0) -> list[dict]:
    """CANDIDATE → JOB (§38): score published jobs, persist matches, return ranked."""
    from app.repositories import jobs_repo
    from app.services.search import JobFilters
    jobs, _total = jobs_repo.list_jobs(JobFilters(per_page=60, sort="freshness"))
    scored: list[dict] = []
    for job in jobs:
        result = match_score(candidate, job)
        if result["score"] < min_score:
            continue
        job = dict(job)
        job["match"] = result
        scored.append(job)
        if user_id:
            store_match(user_id, job["job_id"], result)
    scored.sort(key=lambda j: j["match"]["score"], reverse=True)
    return scored[:limit]
