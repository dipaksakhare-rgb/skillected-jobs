"""Source providers (§2, §51, §106) — API first, RSS second, HTML third.

Each provider returns a list of normalized raw-job dicts:

    {title, company, location, city, url, description, requisition_id,
     posting_date, posting_date_verified, ats_type}

Unknown values stay None — the extraction layer never invents data (§55).
The provider registry lets new ATS systems be added without touching the pipeline.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from urllib.parse import urlparse

from app.crawler.fetcher import Fetcher
from app.services import geo


def detect_city(location: str | None) -> str | None:
    """Free-text location → canonical city, but ONLY for in-scope locations (§3).

    Delegates to the central geo service: Maharashtra cities/localities map to
    their city; India-Remote maps to "Remote"; everything else (other states,
    other countries, bare 'Remote', unknown) returns None so the ingestion gate
    can drop the job — the platform never shows out-of-scope listings.
    """
    if not location:
        return None
    result = geo.normalize_location(location)
    return result[0] if result else None


def _strip_html(raw: str | None) -> str:
    if not raw:
        return ""
    import html as _html
    text = _html.unescape(raw)          # Greenhouse returns escaped HTML
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = _html.unescape(text)         # double-escaped entities
    text = re.sub(r"[ \t\r\n]+", " ", text)
    return text.strip()


def _iso_or_none(value) -> str | None:
    """Normalize ISO strings or epoch-ms to 'YYYY-MM-DD HH:MM:SS'; None otherwise."""
    if not value:
        return None
    if isinstance(value, (int, float)):
        from datetime import datetime, timezone
        ms = value if value > 1e11 else value * 1000  # seconds vs milliseconds
        try:
            return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S")
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value)
    # RFC-2822 (RSS pubDate) → ISO
    if re.search(r"[A-Z]{3}, \d{2} [A-Z]{3} \d{4}", text):
        from datetime import datetime, timezone
        for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"):
            try:
                return datetime.strptime(text[:31], fmt).astimezone(timezone.utc).strftime(
                    "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
        return None
    return text[:19].replace("T", " ")


class ProviderError(Exception):
    """Provider-level failure (bad feed, unreachable API)."""


class BaseProvider(ABC):
    """One provider per source_type/ats_type; resolved via PROVIDER_REGISTRY."""

    ats_type: str = ""

    def __init__(self, fetcher: Fetcher) -> None:
        self.fetcher = fetcher

    @abstractmethod
    def fetch_jobs(self, source: dict) -> list[dict]:
        """Return normalized raw jobs for one career_source row."""


class GreenhouseProvider(BaseProvider):
    """Greenhouse job-board JSON API (Tier 2 ATS)."""

    ats_type = "greenhouse"

    @staticmethod
    def _board_token(source_url: str) -> str:
        # Accept https://boards.greenhouse.io/<token> or ?for=<token> forms.
        parsed = urlparse(source_url)
        qs = dict(p.split("=", 1) for p in parsed.query.split("&") if "=" in p)
        if "for" in qs:
            return qs["for"]
        parts = [p for p in parsed.path.split("/") if p]
        return parts[-1] if parts else ""

    def fetch_jobs(self, source: dict) -> list[dict]:
        token = self._board_token(source["source_url"])
        if not token:
            raise ProviderError("cannot determine Greenhouse board token")
        # Documented public jobs API (stable JSON schema).
        url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
        res = self.fetcher.fetch(url)
        if res.error or res.status != 200:
            raise ProviderError(f"greenhouse fetch failed: {res.error or res.status}")
        try:
            data = json.loads(res.body)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"greenhouse bad JSON: {exc}") from exc
        out: list[dict] = []
        for job in data.get("jobs", []):
            location = (job.get("location") or {}).get("name")
            out.append({
                "title": job.get("title"),
                "company": source.get("company_name"),
                "location": location,
                "city": detect_city(location),
                "url": job.get("absolute_url"),
                "description": _strip_html(job.get("content")),
                "requisition_id": str(job.get("id")) if job.get("id") else None,
                "posting_date": _iso_or_none(job.get("updated_at") or job.get("first_published")),
                "posting_date_verified": bool(job.get("updated_at") or job.get("first_published")),
                "ats_type": self.ats_type,
            })
        return out


class LeverProvider(BaseProvider):
    """Lever postings API (Tier 2 ATS): https://api.lever.co/v0/postings/<co>.json"""

    ats_type = "lever"

    @staticmethod
    def _company(source_url: str) -> str:
        parts = [p for p in urlparse(source_url).path.split("/") if p]
        return parts[0] if parts else ""

    def fetch_jobs(self, source: dict) -> list[dict]:
        company = self._company(source["source_url"])
        if not company:
            raise ProviderError("cannot determine Lever company handle")
        url = f"https://api.lever.co/v0/postings/{company}?mode=json"
        res = self.fetcher.fetch(url)
        if res.error or res.status != 200:
            raise ProviderError(f"lever fetch failed: {res.error or res.status}")
        try:
            data = json.loads(res.body)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"lever bad JSON: {exc}") from exc
        out: list[dict] = []
        for job in data:
            cats = job.get("categories") or {}
            location = job.get("workplaceType") and f"{cats.get('location') or ''} ({job['workplaceType']})" or cats.get("location")
            out.append({
                "title": job.get("text"),
                "company": source.get("company_name"),
                "location": location,
                "city": detect_city(cats.get("location")),
                "url": job.get("hostedUrl") or job.get("applyUrl"),
                "description": _strip_html(job.get("description")),
                "requisition_id": job.get("id"),
                "posting_date": _iso_or_none(job.get("createdAt") / 1000 if job.get("createdAt") else None),
                "posting_date_verified": bool(job.get("createdAt")),
                "ats_type": self.ats_type,
            })
        return out


class SmartRecruitersProvider(BaseProvider):
    """SmartRecruiters public API (Tier 2 ATS)."""

    ats_type = "smartrecruiters"

    @staticmethod
    def _company(source_url: str) -> str:
        parts = [p for p in urlparse(source_url).path.split("/") if p]
        return parts[0] if parts else ""

    def fetch_jobs(self, source: dict) -> list[dict]:
        company = self._company(source["source_url"])
        if not company:
            raise ProviderError("cannot determine SmartRecruiters company id")
        url = f"https://api.smartrecruiters.com/v1/companies/{company}/postings?limit=100"
        res = self.fetcher.fetch(url)
        if res.error or res.status != 200:
            raise ProviderError(f"smartrecruiters fetch failed: {res.error or res.status}")
        try:
            data = json.loads(res.body)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"smartrecruiters bad JSON: {exc}") from exc
        out: list[dict] = []
        for job in data.get("content", []):
            loc = (job.get("location") or {})
            location = ", ".join(str(x) for x in (loc.get("city"), loc.get("region"), loc.get("country")) if x)
            out.append({
                "title": job.get("name"),
                "company": source.get("company_name"),
                "location": location or None,
                "city": detect_city(location),
                "url": f"https://jobs.smartrecruiters.com/{company}/{job.get('id')}" if job.get("id") else None,
                "description": _strip_html((job.get("jobAd") or {}).get("sections", {}).get("jobDescription", {}).get("text")),
                "requisition_id": job.get("id"),
                "posting_date": _iso_or_none(job.get("releasedDate")),
                "posting_date_verified": bool(job.get("releasedDate")),
                "ats_type": self.ats_type,
            })
        return out


class AshbyProvider(BaseProvider):
    """Ashby job board (Tier 2 ATS).

    api.ashbyhq.com returns 401 for robots.txt → full-disallow under RFC 9309,
    so we fetch the PUBLIC BOARD HOST (jobs.ashbyhq.com, robots-allowed) and
    parse the server-rendered `window.__appData` JSON instead. No JS execution;
    no bypassing of access controls — the board page is the public listing.
    """

    ats_type = "ashby"

    @staticmethod
    def _org(source_url: str) -> str:
        parsed = urlparse(source_url)
        parts = [p for p in parsed.path.split("/") if p]
        return parts[-1] if parts else ""

    @staticmethod
    def _extract_app_data(html: str) -> dict:
        marker = "window.__appData = "
        i = html.find(marker)
        if i < 0:
            raise ProviderError("ashby board: __appData not found")
        data, _end = json.JSONDecoder().raw_decode(html[i + len(marker):])
        return data

    def fetch_jobs(self, source: dict) -> list[dict]:
        org = self._org(source["source_url"])
        if not org:
            raise ProviderError("cannot determine Ashby org handle")
        res = self.fetcher.fetch(f"https://jobs.ashbyhq.com/{org}")
        if res.error or res.status != 200:
            raise ProviderError(f"ashby board fetch failed: {res.error or res.status}")
        try:
            data = self._extract_app_data(res.body)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"ashby board bad JSON: {exc}") from exc
        postings = (((data.get("jobBoard") or {}).get("jobPostings")) or [])
        out: list[dict] = []
        for job in postings:
            parts = [str(job.get("locationName") or "")]
            for secondary in job.get("secondaryLocations") or []:
                name = secondary.get("name") if isinstance(secondary, dict) else secondary
                if name:
                    parts.append(str(name))
            location = ", ".join(p for p in parts if p) or None
            job_id = job.get("id")
            out.append({
                "title": job.get("title"),
                "company": source.get("company_name"),
                "location": location,
                "city": detect_city(location),
                "url": f"https://jobs.ashbyhq.com/{org}/{job_id}" if job_id else None,
                "description": "",
                "requisition_id": str(job_id) if job_id else None,
                "posting_date": None,          # board payload carries no publish date
                "posting_date_verified": False,
                "ats_type": self.ats_type,
            })
        return out


class RssFeedProvider(BaseProvider):
    """RSS/Atom career feed (Tier 2/3) — second preference after JSON APIs."""

    ats_type = "rss"

    def fetch_jobs(self, source: dict) -> list[dict]:
        res = self.fetcher.fetch(source["source_url"])
        if res.error or res.status != 200:
            raise ProviderError(f"rss fetch failed: {res.error or res.status}")
        try:
            root = ET.fromstring(res.body)
        except ET.ParseError as exc:
            raise ProviderError(f"rss parse error: {exc}") from exc
        out: list[dict] = []
        for item in root.iter():
            tag = item.tag.split("}")[-1]
            if tag != "item":
                continue
            fields: dict[str, str] = {}
            for child in item:
                fields[child.tag.split("}")[-1]] = (child.text or "").strip()
            link = fields.get("link")
            if not link:
                continue
            out.append({
                "title": fields.get("title"),
                "company": source.get("company_name"),
                "location": fields.get("location"),
                "city": detect_city(fields.get("location")),
                "url": link,
                "description": _strip_html(fields.get("description")),
                "requisition_id": fields.get("guid") or None,
                "posting_date": _iso_or_none(fields.get("pubDate") or fields.get("published")),
                "posting_date_verified": bool(fields.get("pubDate") or fields.get("published")),
                "ats_type": self.ats_type,
            })
        return out


class HtmlCareersProvider(BaseProvider):
    """Generic HTML careers page (Tier 1) — link extraction with title heuristics.

    Conservative: only links whose text looks like a job title become candidates.
    No JS execution; pages that render listings client-side yield nothing rather
    than wrong data (§55 — never invent).
    """

    ats_type = ""

    JOB_LINK_RE = re.compile(
        r"<a[^>]+href=[\"'](?P<href>[^\"']+)[\"'][^>]*>(?P<text>.*?)</a>", re.I | re.S)
    TITLE_WORDS = re.compile(
        r"(engineer|developer|analyst|designer|tester|architect|intern|trainee|"
        r"consultant|administrator|scientist|manager|specialist|associate)", re.I)

    def fetch_jobs(self, source: dict) -> list[dict]:
        res = self.fetcher.fetch(source["source_url"])
        if res.error or res.status != 200:
            raise ProviderError(f"html fetch failed: {res.error or res.status}")
        base = source["source_url"]
        out: list[dict] = []
        seen: set[str] = set()
        for match in self.JOB_LINK_RE.finditer(res.body):
            href = match.group("href")
            text = _strip_html(match.group("text"))
            if not text or not self.TITLE_WORDS.search(text):
                continue
            url = href if href.startswith("http") else (
                f"{base.rstrip('/')}/{href.lstrip('/')}" if href.startswith("/") else None)
            if not url or url in seen:
                continue
            seen.add(url)
            out.append({
                "title": text[:200],
                "company": source.get("company_name"),
                "location": None,
                "city": None,
                "url": url,
                "description": "",
                "requisition_id": None,
                "posting_date": None,
                "posting_date_verified": False,
                "ats_type": "",
            })
        return out


class SitemapJobProvider(BaseProvider):
    """Sitemap-based job discovery (Tier 1 — the sitemap is published for crawlers).

    Parses Radancy-style job URLs: /job/<City>-<Title-Slug>-<PIN>/<id>/.
    City comes from the first slug token; title from the remaining tokens
    (trailing postal code / country token stripped). Optional source-notes
    filter `focus_cities=A,B` restricts ingestion to those cities (§3 focus).
    """

    ats_type = "sitemap"

    JOB_URL_RE = re.compile(r"/job/([^/]+?)/?\d*/?$")

    def _focus_cities(self, source: dict) -> set[str] | None:
        notes = source.get("notes") or ""
        m = re.search(r"focus_cities=([A-Za-z, -]+)", notes)
        if not m:
            return None
        return {c.strip().lower() for c in m.group(1).split(",") if c.strip()}

    def fetch_jobs(self, source: dict) -> list[dict]:
        from urllib.parse import unquote
        res = self.fetcher.fetch(source["source_url"])
        if res.error or res.status != 200:
            raise ProviderError(f"sitemap fetch failed: {res.error or res.status}")
        urls = [unquote(u) for u in re.findall(r"<loc>([^<]+)</loc>", res.body)]
        focus = self._focus_cities(source)
        out: list[dict] = []
        seen: set[str] = set()
        for u in urls:
            m = self.JOB_URL_RE.search(u)
            if not m:
                continue
            slug = m.group(1).strip("/")
            tokens = slug.split("-")
            if len(tokens) < 2:
                continue
            city = tokens[0]
            if focus and city.lower() not in focus:
                continue
            # strip trailing country/PIN tokens from the title (e.g. IND, 411005, IND-411005)
            title_tokens = tokens[1:]
            while title_tokens and (
                    re.fullmatch(r"[A-Z]{2,3}-\d{4,6}", title_tokens[-1] or "")
                    or re.fullmatch(r"[A-Z]{2,3}", title_tokens[-1] or "")
                    or re.fullmatch(r"\d{4,6}", title_tokens[-1] or "")):
                title_tokens.pop()
            title = " ".join(title_tokens).strip()
            job_id_m = re.search(r"/(\d{6,})/?$", u)
            if not title or u in seen:
                continue
            seen.add(u)
            out.append({
                "title": title.replace("-", " ").strip(),
                "company": source.get("company_name"),
                "location": city,
                "city": detect_city(city),
                "url": u,
                "description": "",
                "requisition_id": job_id_m.group(1) if job_id_m else None,
                "posting_date": None,   # sitemap carries no dates (§7 → First seen)
                "posting_date_verified": False,
                "ats_type": self.ats_type,
            })
        return out


PROVIDER_REGISTRY: dict[str, type[BaseProvider]] = {
    "greenhouse": GreenhouseProvider,
    "lever": LeverProvider,
    "smartrecruiters": SmartRecruitersProvider,
    "ashby": AshbyProvider,
    "rss": RssFeedProvider,
    "html": HtmlCareersProvider,
    "sitemap": SitemapJobProvider,
}


def resolve_provider(source: dict, fetcher: Fetcher) -> BaseProvider:
    """Pick the provider for a source row (§106 seam: add a class + registry row)."""
    ats = (source.get("ats_type") or "").strip().lower()
    if ats in PROVIDER_REGISTRY:
        return PROVIDER_REGISTRY[ats](fetcher)
    if (source.get("source_type") or "") == "official_careers":
        return HtmlCareersProvider(fetcher)
    raise ProviderError(f"no provider for source {source.get('source_id')}")
