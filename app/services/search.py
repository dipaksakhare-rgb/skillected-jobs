"""Search service (§58–59, §92) — whitelisted filters, parameterized SQL, role expansion."""
from __future__ import annotations

from dataclasses import dataclass, field

ROLE_SYNONYMS: dict[str, list[str]] = {
    # §35 semantic equivalence — resume terms → searchable role tokens.
    "react developer": ["frontend developer", "react js developer", "ui developer",
                        "javascript developer", "mern developer", "software engineer"],
    "frontend developer": ["react developer", "ui developer", "javascript developer",
                           "web developer"],
    "python developer": ["backend developer", "django developer", "software engineer"],
    "data analyst": ["bi analyst", "reporting analyst", "business analyst",
                     "data visualization analyst", "analytics"],
    "devops engineer": ["cloud engineer", "sre", "platform engineer",
                        "cloud support engineer", "site reliability engineer"],
    "qa engineer": ["software tester", "automation tester", "sdet", "test engineer"],
    "cybersecurity analyst": ["soc analyst", "security analyst", "security engineer"],
    "embedded engineer": ["embedded software engineer", "firmware engineer",
                          "iot engineer"],
    "business analyst": ["functional analyst", "product analyst", "requirements analyst",
                         "data analyst"],
    "full stack developer": ["software developer", "software engineer", "web developer",
                             "mern developer"],
}
_SYNONYM_INDEX: dict[str, list[str]] = {}
for _role, _alts in ROLE_SYNONYMS.items():
    for _a in _alts:
        _SYNONYM_INDEX.setdefault(_a, []).append(_role)

FRESHER_KEYWORDS = ["fresher", "graduate", "trainee", "intern", "apprentice", "junior",
                    "associate", "entry level", "get", "graduate engineer trainee",
                    "software engineer i", "analyst", "support engineer", "qa trainee"]


@dataclass
class JobFilters:
    q: str = ""
    city: str = ""
    domain: str = ""
    company: str = ""
    experience_min: float | None = None
    experience_max: float | None = None
    fresher: bool = False
    work_mode: str = ""
    employment_type: str = ""
    posted_within: str = ""      # key from freshness.POSTED_FILTERS
    verified_only: bool = False
    salary_only: bool = False
    sort: str = "freshness"
    page: int = 1
    per_page: int = 20
    extra_terms: list[str] = field(default_factory=list)  # semantic expansions


def expand_role(query: str) -> list[str]:
    """Return extra search terms from semantic role equivalence (§35)."""
    ql = query.lower().strip()
    extras: list[str] = []
    for role, alts in ROLE_SYNONYMS.items():
        if role in ql:
            extras.extend(a for a in alts if a not in ql)
    for alt, roles in _SYNONYM_INDEX.items():
        if alt in ql:
            extras.extend(r for r in roles if r not in ql)
    return list(dict.fromkeys(extras))


def looks_fresher_query(query: str) -> bool:
    ql = query.lower()
    return any(k in ql for k in FRESHER_KEYWORDS)


def parse_filters(params) -> JobFilters:
    """Build JobFilters from a request query-params mapping (FastAPI QueryParams)."""
    def g(key: str) -> str:
        return (params.get(key) or "").strip()

    def fnum(key: str) -> float | None:
        raw = g(key)
        try:
            return float(raw) if raw else None
        except ValueError:
            return None

    page = max(1, int(g("page") or 1))
    per_page = min(50, max(5, int(g("per_page") or 20)))
    return JobFilters(
        q=g("q")[:200], city=g("city")[:80], domain=g("domain")[:80], company=g("company")[:80],
        experience_min=fnum("experience_min"), experience_max=fnum("experience_max"),
        fresher=g("fresher") in ("1", "true", "on"),
        work_mode=g("work_mode")[:20], employment_type=g("employment_type")[:20],
        posted_within=g("posted_within")[:5], verified_only=g("verified_only") in ("1", "true", "on"),
        salary_only=g("salary_only") in ("1", "true", "on"),
        sort=g("sort") or "freshness", page=page, per_page=per_page,
    )
