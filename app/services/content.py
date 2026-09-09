"""Content generation (§15–17): WhatsApp text, QR codes, QR poster.

QR targets the tracking URL /apply/{job_id} — final destination is always the
company application page (§14). Poster generation service lands in Phase 3;
Phase 1 ships QR + WhatsApp + a poster-ready share page.
"""
from __future__ import annotations

import io
from urllib.parse import quote

import qrcode  # type: ignore[import-untyped]
import qrcode.image.svg  # type: ignore[import-untyped]


def whatsapp_message(job: dict, apply_url: str) -> str:
    """§17 template — exactly the specified fields, 'Not specified' when unknown (§86)."""
    def val(key: str) -> str:
        v = job.get(key)
        return str(v).strip() if v not in (None, "") else "Not specified"

    skills = job.get("skills") or job.get("skills_list") or []
    skills_text = ", ".join(skills) if isinstance(skills, list) else str(skills or "Not specified")
    exp = job.get("experience_text") or _experience_text(job)
    return (
        "🚨 NEW IT JOB OPPORTUNITY\n\n"
        f"🏢 Company: {val('company_name')}\n\n"
        f"💼 Role: {val('job_title')}\n\n"
        f"📍 Location: {val('location')}\n\n"
        f"👨‍💻 Experience: {exp}\n\n"
        "🧠 Skills:\n"
        f"{skills_text or 'Not specified'}\n\n"
        "💰 Salary:\n"
        f"{val('salary_display')}\n\n"
        "🕒 Posted:\n"
        f"{val('time_label')}\n\n"
        "✓ Verified Company Opening\n\n"
        f"🔗 Apply Directly:\n{apply_url}\n\n"
        "📲 Scan the QR code on the poster to apply directly.\n\n"
        "⚠️ Apply only through the official company application link.\n\n"
        "#SkillectedJobs #MaharashtraJobs #PuneJobs #ITJobs #FresherJobs"
    )


def _experience_text(job: dict) -> str:
    mn, mx = job.get("experience_min"), job.get("experience_max")
    if mn is None and mx is None:
        return "Not specified"
    if mx is None:
        return f"{_fmt(mn)}+ years"
    return f"{_fmt(mn)}–{_fmt(mx)} years"


def _fmt(v: float | None) -> str:
    if v is None:
        return "0"
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


def qr_svg(data: str) -> bytes:
    """Server-side QR generation as SVG (§15)."""
    img = qrcode.make(data, image_factory=qrcode.image.svg.SvgPathImage, box_size=12,
                      border=2)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue()


def qr_png(data: str) -> bytes:
    img = qrcode.make(data, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def poster_share_text(job: dict) -> str:
    return f"SCAN TO APPLY — {job.get('job_title', 'Job')} @ {job.get('company_name', '')}"


def whatsapp_share_url(apply_url: str, message: str) -> str:
    return f"https://wa.me/?text={quote(f'{message}\n\n{apply_url}')}"
