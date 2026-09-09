from app.services import content


def _job(**over):
    job = {"company_name": "Persistent Systems", "job_title": "Software Engineer",
           "location": "Pune", "experience_text": "1–3 years",
           "skills": ["Java", "Spring Boot"], "salary_display": "9,00,000 – 14,00,000 INR/year",
           "time_label": "Posted 32 minutes ago"}
    job.update(over)
    return job


def test_whatsapp_template_fields():
    msg = content.whatsapp_message(_job(), "https://jobs.skillected.com/apply/1")
    assert "🏢 Company: Persistent Systems" in msg
    assert "💼 Role: Software Engineer" in msg
    assert "📍 Location: Pune" in msg
    assert "👨‍💻 Experience: 1–3 years" in msg
    assert "Java, Spring Boot" in msg
    assert "✓ Verified Company Opening" in msg
    assert "https://jobs.skillected.com/apply/1" in msg
    assert "#SkillectedJobs #PuneJobs #ITJobs #FreshersJobs" in msg
    assert "⚠️ Apply only through the official company application link." in msg


def test_whatsapp_unknown_becomes_not_specified():
    msg = content.whatsapp_message(_job(salary_display=None, location=None),
                                   "https://jobs.skillected.com/apply/1")
    assert "Not specified" in msg


def test_qr_svg_generation():
    svg = content.qr_svg("https://jobs.skillected.com/apply/1")
    assert svg.startswith(b"<") and b"svg" in svg.lower()


def test_qr_png_generation():
    png = content.qr_png("https://jobs.skillected.com/apply/1")
    assert png.startswith(b"\x89PNG")


def test_share_url_escaping():
    url = content.whatsapp_share_url("https://x/apply/1", "hello")
    assert url.startswith("https://wa.me/?text=")
