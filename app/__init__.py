"""Skillected Jobs — FastAPI application factory."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.security import limiter, client_ip
from app.routers import admin, api, candidate, insights, public

settings = get_settings()
log = logging.getLogger("skillected")


def _humanize_minutes(minutes: float | None) -> str:
    if minutes is None:
        return ""
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{int(minutes)} min ago"
    hours = minutes / 60
    if hours < 24:
        h = int(hours)
        return f"{h} hour{'s' if h != 1 else ''} ago"
    days = int(hours // 24)
    return f"{days} day{'s' if days != 1 else ''} ago"


templates = Jinja2Templates(directory=str(settings.templates_dir))
templates.env.filters["humanize"] = _humanize_minutes
templates.env.globals["APP_NAME"] = "Skillected Jobs"
templates.env.globals["TAGLINE"] = "Verified IT Opportunities. Direct Company Applications."


def _parse_json(value: str | None):
    if not value:
        return []
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []


templates.env.filters["fromjson"] = _parse_json


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; frame-ancestors 'none'",
        )
        if settings.is_prod:
            response.headers.setdefault("Strict-Transport-Security", "max-age=63072000")
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    LIMITS = {"/admin/login": (10, 300), "/api/": (240, 60)}

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        for prefix, (limit, window) in self.LIMITS.items():
            if path.startswith(prefix):
                if not limiter.check(prefix, client_ip(request), limit, window):
                    return JSONResponse(
                        {"error": {"code": "rate_limited", "message": "Too many requests"}},
                        status_code=429,
                    )
                break
        return await call_next(request)


def create_app() -> FastAPI:
    app = FastAPI(title="Skillected Jobs", version="0.1.0",
                  description="Verified IT Opportunities. Direct Company Applications.")
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware)

    static_path = Path(settings.static_dir)
    static_path.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    app.include_router(public.router)
    app.include_router(insights.router)
    app.include_router(api.router)
    app.include_router(candidate.router)
    app.include_router(admin.router)

    @app.middleware("http")
    async def attach_session(request: Request, call_next):
        from app.core.security import get_session
        request.scope["session_data"] = get_session(request)
        return await call_next(request)

    if settings.app_env != "test":
        from app.crawler.scheduler import start_scheduler
        start_scheduler()

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}

    @app.get("/bot", response_class=JSONResponse)
    def bot_info() -> dict:
        """Crawler identification page referenced in our User-Agent (§51)."""
        return {
            "name": "SkillectedJobsBot",
            "purpose": "Indexes public career pages/ATS feeds to link verified openings with direct application URLs.",
            "contact": "https://www.skillected.com/",
            "respect": ["robots.txt", "rate limits", "terms of service"],
        }

    return app
