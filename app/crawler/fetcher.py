"""Polite HTTP fetching layer (§51).

Respects robots.txt, per-source rate limits and access restrictions. Never
bypasses CAPTCHA, authentication, anti-bot protections, paywalls or access
controls. Plain HTTP GET only — no remote JavaScript execution.
"""
from __future__ import annotations

import logging
import time
import urllib.robotparser
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

log = logging.getLogger("skillected.crawler")

USER_AGENT = "SkillectedJobsBot/1.0 (+https://jobs.skillected.com/bot; respectful crawler)"


@dataclass
class FetchResult:
    url: str
    status: int | None
    body: str
    error: str = ""
    content_type: str = ""
    from_robots: bool = False  # True → blocked by robots.txt (not an error)


@dataclass
class _RateBucket:
    min_interval: float
    last: float = 0.0


class RobotsCache:
    """robots.txt parser cache keyed by origin.

    We fetch robots.txt ourselves (with our identified UA) instead of letting
    urllib's default UA do it: some CDNs 403 the default urllib UA on robots.txt,
    which RFC 9309 interprets as full-disallow even though the site's actual
    directives permit us. Directives are still honored exactly.
    """

    def __init__(self, timeout: float = 10.0) -> None:
        self._cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._timeout = timeout

    def allowed(self, url: str) -> bool:
        parts = urlparse(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._cache:
            rp = urllib.robotparser.RobotFileParser()
            try:
                resp = httpx.get(f"{origin}/robots.txt",
                                 headers={"User-Agent": USER_AGENT},
                                 timeout=self._timeout, follow_redirects=True)
                if resp.status_code == 200 and "text/" in resp.headers.get("content-type", "text/plain"):
                    rp.parse(resp.text.splitlines())
                elif resp.status_code in (401, 403):
                    rp.disallow_all = True   # RFC 9309: unreachable/protected → disallow
                else:
                    rp.allow_all = True      # 404/410/other 4xx → unrestricted
                self._cache[origin] = rp
            except Exception as exc:  # noqa: BLE001 — network error: allow with per-source delay
                log.warning("robots.txt unreachable for %s (%s); allowing with delay", origin, exc)
                self._cache[origin] = None
        rp = self._cache[origin]
        return True if rp is None else rp.can_fetch(USER_AGENT, url)


class Fetcher:
    """Shared HTTP fetcher with global politeness delay + robots.txt enforcement."""

    def __init__(self, timeout: float = 20.0, min_interval: float = 2.0,
                 max_bytes: int = 30_000_000) -> None:
        self.robots = RobotsCache(timeout)
        self._bucket = _RateBucket(min_interval=min_interval)
        self._timeout = timeout
        self._max_bytes = max_bytes

    def _throttle(self) -> None:
        wait = self._bucket.min_interval - (time.monotonic() - self._bucket.last)
        if wait > 0:
            time.sleep(wait)
        self._bucket.last = time.monotonic()

    def fetch(self, url: str, respect_robots: bool = True) -> FetchResult:
        if respect_robots and not self.robots.allowed(url):
            log.info("robots.txt disallows %s — skipping", url)
            return FetchResult(url=url, status=None, body="", from_robots=True)
        self._throttle()
        try:
            with httpx.Client(timeout=self._timeout, follow_redirects=True,
                              headers={"User-Agent": USER_AGENT}) as client:
                resp = client.get(url)
            ctype = resp.headers.get("content-type", "")
            body = resp.text[: self._max_bytes]
            return FetchResult(url=str(resp.url), status=resp.status_code, body=body,
                               content_type=ctype)
        except Exception as exc:  # noqa: BLE001 — network errors are per-source, not fatal
            log.warning("fetch failed %s: %s", url, exc)
            return FetchResult(url=url, status=None, body="", error=str(exc))
