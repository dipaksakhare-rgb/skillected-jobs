"""Security core (§66): password hashing, sessions, RBAC, CSRF, rate limiting."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, Form, status

from app.core import database as db
from app.core.config import get_settings
from app.repositories import users_repo

_settings = get_settings()

PBKDF2_ITERATIONS = 200_000


# ---------------------------------------------------------------- passwords

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex),
                                 int(iterations))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------- sessions

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def create_session(user_id: int) -> tuple[str, str]:
    """Returns (session_token, csrf_token)."""
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    roles = users_repo.user_roles(user_id)
    ttl = (_settings.session_ttl_hours_admin if "admin" in roles
           else _settings.session_ttl_hours_user)
    expires = (datetime.now(timezone.utc) + timedelta(hours=ttl)).strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "INSERT INTO sessions (session_id, user_id, csrf_token, expires_at) VALUES (?,?,?,?)",
        (token, user_id, csrf, expires),
    )
    return token, csrf


def get_session(request: Request) -> dict | None:
    token = request.cookies.get(_settings.session_cookie)
    if not token:
        return None
    row = db.query_one(
        """SELECT s.session_id, s.user_id, s.csrf_token, s.expires_at, u.email
           FROM sessions s JOIN users u ON u.user_id = s.user_id
           WHERE s.session_id = ? AND u.is_active = 1""",
        (token,),
    )
    if not row or row["expires_at"] < _now_iso():
        return None
    sess = dict(row)
    sess["roles"] = users_repo.user_roles(int(row["user_id"]))
    return sess


def destroy_session(request: Request) -> None:
    token = request.cookies.get(_settings.session_cookie)
    if token:
        db.execute("DELETE FROM sessions WHERE session_id = ?", (token,))


# ---------------------------------------------------------------- RBAC deps

def current_user(request: Request) -> dict | None:
    return get_session(request)


def require_role(*roles: str) -> Callable:
    """Dependency: 401 if not logged in, 403 if role missing."""

    def dependency(request: Request) -> dict:
        sess = get_session(request)
        if not sess:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required")
        if roles and not (set(sess["roles"]) & set(roles)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return sess

    return dependency


# ---------------------------------------------------------------- CSRF

def csrf_token(request: Request) -> str:
    sess = get_session(request)
    if sess:
        return sess["csrf_token"]
    # anonymous double-submit token (e.g. report-job form)
    return request.cookies.get("skillected_csrf", "")


def verify_csrf(request: Request, submitted: str) -> None:
    sess = get_session(request)
    expected = sess["csrf_token"] if sess else request.cookies.get("skillected_csrf", "")
    if not expected or not hmac.compare_digest(expected, submitted or ""):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token invalid")


async def csrf_form_field(request: Request) -> str:
    """FastAPI dependency extracting _csrf from a form body."""
    form = await request.form()
    return str(form.get("_csrf", ""))


def ensure_anon_csrf_cookie(response, request: Request) -> None:
    if not request.cookies.get("skillected_csrf"):
        response.set_cookie("skillected_csrf", secrets.token_urlsafe(24),
                            httponly=True, samesite="lax")


# ---------------------------------------------------------------- rate limiting

class RateLimiter:
    """Sliding-window limiter keyed by (bucket, client_ip). Prod: swap to Redis."""

    def __init__(self) -> None:
        self._hits: dict[tuple[str, str], list[float]] = {}

    def check(self, bucket: str, ip: str, limit: int, window_seconds: int) -> bool:
        now = time.time()
        key = (bucket, ip)
        hits = [t for t in self._hits.get(key, []) if now - t < window_seconds]
        if len(hits) >= limit:
            self._hits[key] = hits
            return False
        hits.append(now)
        self._hits[key] = hits
        return True


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?")
