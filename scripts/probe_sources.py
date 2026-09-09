"""One-off probe: check public ATS board APIs for Pune/India jobs.

Uses the same public JSON endpoints our providers use. Read-only GETs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import httpx

UA = {"User-Agent": "SkillectedJobsBot/1.0 (+https://jobs.skillected.com/bot)"}

PUNE_WORDS = ("pune", "pcmc", "hinjewadi", "kharadi", "baner", "wakad", "magarpatta")
INDIA_WORDS = ("india", "bangalore", "bengaluru", "mumbai", "nagpur", "nashik", "hyderabad", "gurugram", "gurgaon", "noida", "delhi", "chennai", "remote")

GREENHOUSE = ["speechify", "arkoselabs", "digicert", "orioninnovation", "connectwise", "udemy", "securly13", "inovalon", "addepar1"]
LEVER = ["pattern", "gohighlevel"]
ASHBY = ["opengov", "ema", "ontic", "certifyos", "replit", "elevenlabs"]


def probe_greenhouse(token: str) -> None:
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=false"
    try:
        r = httpx.get(url, headers=UA, timeout=20, follow_redirects=True)
        if r.status_code != 200:
            print(f"GH {token}: HTTP {r.status_code}")
            return
        jobs = r.json().get("jobs", [])
        india = [j for j in jobs if any(w in (j.get("location") or {}).get("name", "").lower() for w in INDIA_WORDS + PUNE_WORDS)]
        pune = [j for j in india if any(w in (j.get("location") or {}).get("name", "").lower() for w in PUNE_WORDS)]
        print(f"GH {token}: total={len(jobs)} india={len(india)} pune={len(pune)}")
        for j in pune[:4]:
            print(f"   PUNE: {j['title']}  |  {(j.get('location') or {}).get('name')}")
    except Exception as exc:
        print(f"GH {token}: ERROR {exc}")


def probe_lever(token: str) -> None:
    url = f"https://api.lever.co/v0/postings/{token}?mode=json"
    try:
        r = httpx.get(url, headers=UA, timeout=20, follow_redirects=True)
        if r.status_code != 200:
            print(f"LEVER {token}: HTTP {r.status_code}")
            return
        jobs = r.json()
        def loc(j):
            return (j.get("categories") or {}).get("location") or ""
        india = [j for j in jobs if any(w in loc(j).lower() for w in INDIA_WORDS + PUNE_WORDS)]
        pune = [j for j in india if any(w in loc(j).lower() for w in PUNE_WORDS)]
        print(f"LEVER {token}: total={len(jobs)} india={len(india)} pune={len(pune)}")
        for j in pune[:4]:
            print(f"   PUNE: {j['text']}  |  {loc(j)}")
    except Exception as exc:
        print(f"LEVER {token}: ERROR {exc}")


def probe_ashby(org: str) -> None:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{org}"
    try:
        r = httpx.get(url, headers=UA, timeout=20, follow_redirects=True)
        if r.status_code != 200:
            print(f"ASHBY {org}: HTTP {r.status_code}")
            return
        jobs = r.json().get("jobs", [])
        def loc(j):
            l = j.get("location")
            if isinstance(l, dict):
                return str(l.get("locationHint") or l.get("name") or "")
            return str(l or "")
        india = [j for j in jobs if any(w in loc(j).lower() for w in INDIA_WORDS + PUNE_WORDS)]
        pune = [j for j in india if any(w in loc(j).lower() for w in PUNE_WORDS)]
        print(f"ASHBY {org}: total={len(jobs)} india={len(india)} pune={len(pune)}")
        for j in pune[:4]:
            print(f"   PUNE: {j['title']}  |  {loc(j)}")
    except Exception as exc:
        print(f"ASHBY {org}: ERROR {exc}")


if __name__ == "__main__":
    for t in GREENHOUSE:
        probe_greenhouse(t)
    for t in LEVER:
        probe_lever(t)
    for t in ASHBY:
        probe_ashby(t)
