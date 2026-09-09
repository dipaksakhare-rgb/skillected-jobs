"""Geographic scope (§3): Skillected serves Maharashtra (Pune-first) IT hiring.

Single source of truth for every location decision on the platform:

- ``normalize_location()`` — free-text location → ``(city, state)`` when the job
  is in-scope (a Maharashtra city, or explicitly Remote-India), else ``None``.
- ``is_maharashtra()``    — scope test used by ingestion gating and backfills.

Out-of-scope = other Indian states, other countries, and bare "Remote" (which in
ATS data overwhelmingly means a US remote pool). Never guess: an unknown location
is out of scope, not Maharashtra (§55 — never invent).
"""
from __future__ import annotations

import re

MH_STATE = "Maharashtra"

# Neighborhoods / campuses that fold into a canonical city.
_LOCALITY_TO_CITY: dict[str, str] = {
    # Pune + PCMC
    "hinjewadi": "Pune", "hinjawadi": "Pune", "wakad": "Pune", "baner": "Pune",
    "kharadi": "Pune", "viman nagar": "Pune", "magarpatta": "Pune",
    "hadapsar": "Pune", "yerwada": "Pune", "kalyani nagar": "Pune",
    "koregaon park": "Pune", "shivajinagar": "Pune", "aundh": "Pune",
    "balewadi": "Pune", "talegaon": "Pune", "chakan": "Pune",
    "ranjangaon": "Pune", "pirangut": "Pune", "kothrud": "Pune",
    "pimpri": "Pimpri-Chinchwad", "chinchwad": "Pimpri-Chinchwad",
    "pcmc": "Pimpri-Chinchwad", "akurdi": "Pimpri-Chinchwad",
    # Mumbai region
    "andheri": "Mumbai", "powai": "Mumbai", "worli": "Mumbai",
    "bandra kurla complex": "Mumbai", "lower parel": "Mumbai",
    "vashi": "Navi Mumbai", "kharghar": "Navi Mumbai", "belapur": "Navi Mumbai",
    "airoli": "Navi Mumbai", "ghansoli": "Navi Mumbai", "rabale": "Navi Mumbai",
    "mahape": "Navi Mumbai", "powai lake": "Mumbai",
}

# Canonical Maharashtra cities we index: lowercase key → display name.
MAHARASHTRA_CITIES: dict[str, str] = {
    "pune": "Pune", "pimpri-chinchwad": "Pimpri-Chinchwad",
    "mumbai": "Mumbai", "navi mumbai": "Navi Mumbai", "thane": "Thane",
    "nashik": "Nashik", "nagpur": "Nagpur",
    "chhatrapati sambhajinagar": "Chhatrapati Sambhajinagar",
    "aurangabad": "Chhatrapati Sambhajinagar",
    "kolhapur": "Kolhapur", "solapur": "Solapur", "amravati": "Amravati",
    "akola": "Akola", "jalgaon": "Jalgaon", "nanded": "Nanded",
    "latur": "Latur", "ahmednagar": "Ahmednagar", "satara": "Satara",
    "sangli": "Sangli", "palghar": "Palghar", "ratnagiri": "Ratnagiri",
    "alibag": "Alibag", "dhule": "Dhule", "chandrapur": "Chandrapur",
    "wardha": "Wardha", "yavatmal": "Yavatmal", "beed": "Beed",
    "osmanabad": "Osmanabad", "gondia": "Gondia", "washim": "Washim",
    "buldhana": "Buldhana", "jalna": "Jalna", "parbhani": "Parbhani",
    "hingoli": "Hingoli", "gadchiroli": "Gadchiroli", "nandurbar": "Nandurbar",
    "sindhudurg": "Sindhudurg", "raigad": "Raigad",
}

# India-wide tokens that prove the job IS in India but OUTSIDE Maharashtra.
_OTHER_INDIA_RE = re.compile(
    r"\b(bangalore|bengaluru|hyderabad|chennai|gurgaon|gurugram|noida|delhi|"
    r"new delhi|kolkata|jaipur|ahmedabad|indore|bhopal|chandigarh|kochi|"
    r"coimbatore|mysore|vizag|vishakhapatnam|karnataka|telangana|tamil nadu|"
    r"kerala|gujarat|madhya pradesh|uttar pradesh|haryana|punjab|rajasthan|"
    r"west bengal|odisha|orissa|assam|bihar|jharkhand|chhattisgarh|goa|"
    r"andhra pradesh|uttarakhand|himachal|jammu|kashmir|tripura|manipur|"
    r"meghalaya|nagaland|sikkim|arunachal)\b", re.I)

# Foreign-country tokens (country names + common short codes).
_FOREIGN_RE = re.compile(
    r"\b(usa|us|united states|america|uk|united kingdom|england|london|"
    r"canada|toronto|vancouver|mexico|brazil|colombia|bogota|sao paulo|"
    r"argentina|chile|poland|warsaw|krakow|romania|bucharest|ukraine|"
    r"germany|berlin|munich|france|paris|spain|madrid|barcelona|italy|milan|"
    r"netherlands|amsterdam|sweden|stockholm|norway|oslo|denmark|copenhagen|"
    r"finland|ireland|dublin|scotland|edinburgh|wales|israel|tel aviv|"
    r"uae|dubai|abu dhabi|qatar|doha|saudi|singapore|malaysia|philippines|"
    r"manila|indonesia|jakarta|vietnam|hanoi|thailand|bangkok|japan|tokyo|"
    r"osaka|china|beijing|shanghai|shenzhen|korea|seoul|taiwan|taipei|"
    r"hong kong|australia|sydney|melbourne|brisbane|perth|new zealand|auckland|"
    r"south africa|cape town|johannesburg|kenya|nairobi|egypt|cairo|nigeria|"
    r"lagos|europe|emea|apac|latam|americas)\b", re.I)

# A token meaning "in India" when nothing more specific matches.
_INDIA_RE = re.compile(r"\bindia\b|\bind\b", re.I)

_REMOTE_RE = re.compile(r"\bremote\b|work from home|wfh|anywhere", re.I)


def _word_hit(text: str, tokens) -> str | None:
    """First whole-word hit, longest token first (Navi Mumbai before Mumbai)."""
    for t in sorted(tokens, key=len, reverse=True):
        if re.search(rf"\b{re.escape(t)}\b", text):
            return t
    return None


def normalize_location(text: str | None) -> tuple[str, str | None] | None:
    """Free-text location → (canonical_city, state) if in scope, else None.

    Returns ("Remote", None) only for explicitly India-remote listings.
    """
    if not text:
        return None
    low = " ".join(str(text).lower().split())

    # In-scope city/locality match wins first: ATS strings like "US | Pune |
    # Hinjewadi" or "Bangalore, IN ; Pune, IN" contain a Maharashtra city and
    # ARE relevant to Maharashtra candidates, whatever else the string mentions.
    # ("Bangalore; Pune" is one requisition with multiple offices — Pune counts.)
    locality = _word_hit(low, _LOCALITY_TO_CITY)
    if locality:
        return (_LOCALITY_TO_CITY[locality], MH_STATE)

    city = _word_hit(low, MAHARASHTRA_CITIES)
    if city:
        return (MAHARASHTRA_CITIES[city], MH_STATE)

    # No Maharashtra city anywhere in the string → apply the out-of-scope rules.
    # Foreign country anywhere → out of scope.
    if _FOREIGN_RE.search(low):
        return None

    # India but outside Maharashtra → out of scope.
    if _OTHER_INDIA_RE.search(low):
        return None

    # Explicit India-remote stays visible (relevant to Maharashtra candidates);
    # bare "Remote" (usually a US pool in ATS data) does not.
    if _REMOTE_RE.search(low):
        if _INDIA_RE.search(low):
            return ("Remote", None)
        return None

    if _INDIA_RE.search(low):
        # India without a state we can verify — not provably Maharashtra.
        return None
    return None


def is_maharashtra(text: str | None) -> bool:
    return normalize_location(text) is not None


# SQL scope fragment for the jobs table (alias ``j``): a job is visible on the
# public platform only when ingestion recorded an in-scope canonical city
# (Maharashtra city or "Remote" for explicit India-remote). City IS NULL means
# out-of-scope or pre-scope data → hidden everywhere until the backfill rules it.
SCOPE_SQL = "j.city IS NOT NULL"
