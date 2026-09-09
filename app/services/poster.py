"""Poster PNG generation (§16, Phase 3) — 1080×1350 using Pillow.

Deterministic brand rendering; the HTML poster page remains the interactive
variant. Providers can be swapped via STORAGE_BACKEND (§106).
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw

from app.core.config import get_settings

settings = get_settings()

W, H = 1080, 1350


def _font(size: int, bold: bool = True):
    from PIL import ImageFont
    for name in (("segoeuib.ttf" if bold else "segoeui.ttf"), "arialbd.ttf" if bold else "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def poster_png(job: dict, apply_url: str, qr_png_bytes: bytes) -> bytes:
    """Render the §16 poster: brand, kicker, company, title, meta chips, QR, footer."""
    img = Image.new("RGB", (W, H), (11, 18, 32))
    # subtle vertical gradient
    for y in range(H):
        blend = y / H
        r = int(11 + (16 - 11) * blend)
        g = int(18 + (34 - 18) * blend)
        b = int(32 + (74 - 32) * blend)
        ImageDraw.Draw(img).line([(0, y), (W, y)], fill=(r, g, b))
    draw = ImageDraw.Draw(img)

    margin = 72
    ink = (255, 255, 255)
    soft = (157, 184, 255)

    # brand row
    f_brand = _font(34)
    draw.rectangle([margin, 66, margin + 46, 112], fill=(11, 95, 255))
    draw.text((margin + 62, 70), "SKILLECTED JOBS", font=f_brand, fill=ink)
    draw.text((W - margin - 190, 70), "NEW OPPORTUNITY", font=_font(24), fill=soft)

    # kicker
    y = 210
    draw.text((margin, y), "NEW IT JOB OPPORTUNITY", font=_font(26), fill=soft)
    y += 64

    # company + title
    f_company = _font(30)
    draw.text((margin, y), str(job.get("company_name") or "")[:48], font=f_company, fill=(207, 224, 255))
    y += 58
    f_title = _font(64)
    for line in _wrap(draw, str(job.get("job_title") or "Job Opening"), f_title, W - 2 * margin)[:3]:
        draw.text((margin, y), line, font=f_title, fill=ink)
        y += 74

    # meta chips
    y += 16
    f_chip = _font(26)
    chips = [f"📍 {job.get('city') or 'India'}",
             f"👨‍💻 {job.get('experience_text') or 'Experience not specified'}"]
    if job.get("salary_display"):
        chips.append(f"💰 {job['salary_display']}")
    for chip in chips[:3]:
        wtxt = draw.textlength(chip, font=f_chip)
        draw.rounded_rectangle([margin, y, margin + wtxt + 36, y + 52], radius=26,
                               outline=(255, 255, 255, 60), width=2)
        draw.text((margin + 18, y + 10), chip, font=f_chip, fill=ink)
        y += 66

    # skills line
    skills = job.get("skills_list") or []
    if skills:
        y += 8
        draw.text((margin, y), "🧠 " + " · ".join(skills[:5]), font=_font(26), fill=(207, 224, 255))

    # verification + freshness
    y += 66
    verify = "✓ Verified Company Opening" if job.get("job_status") == "active" else "Application closed"
    draw.text((margin, y), verify, font=_font(28, bold=True), fill=(120, 220, 160))
    if job.get("time_label"):
        draw.text((margin, y + 44), job["time_label"], font=_font(24), fill=soft)

    # QR block
    from io import BytesIO
    qr = Image.open(BytesIO(qr_png_bytes)).convert("RGB")
    qr_size = 330
    qr = qr.resize((qr_size, qr_size))
    qx, qy = W - margin - qr_size, H - 420
    draw.rounded_rectangle([qx - 18, qy - 18, qx + qr_size + 18, qy + qr_size + 18],
                           radius=18, fill=(255, 255, 255))
    img.paste(qr, (qx, qy))
    draw.text((qx - 6, qy + qr_size + 30), "SCAN TO APPLY", font=_font(26, bold=True), fill=ink)

    # CTA text (left of QR)
    cta_y = qy + 40
    draw.text((margin, cta_y), "APPLY", font=_font(56), fill=ink)
    draw.text((margin, cta_y + 70), "DIRECTLY", font=_font(56), fill=ink)
    draw.text((margin, cta_y + 160), "Official company application", font=_font(24), fill=soft)
    try:
        draw.text((margin, cta_y + 196), apply_url.replace("https://", "")[:44], font=_font(20), fill=soft)
    except Exception:  # noqa: BLE001 — URL drawing is best-effort
        pass

    # footer
    draw.line([(margin, H - 110), (W - margin, H - 110)], fill=(60, 80, 130), width=2)
    draw.text((margin, H - 92), "Verified IT Opportunities for Students & Professionals",
              font=_font(24), fill=soft)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def save_poster(job_id: int, png: bytes) -> Path:
    """Persist under data/posters and register in poster_assets."""
    out_dir = settings.data_dir / "posters"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"poster-{job_id}.png"
    path.write_bytes(png)
    from app.core import database as db
    db.execute(
        """INSERT INTO poster_assets (job_id, storage_path, width, height)
           VALUES (?,?,?,?)
           ON CONFLICT(job_id, storage_path) DO NOTHING""",
        (job_id, str(path), W, H),
    )
    return path
