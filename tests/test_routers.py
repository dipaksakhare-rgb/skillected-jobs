"""Router integration tests (§83: API tests, auth tests, apply redirect, expiry)."""


def test_home_page_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Start Your IT Career in Pune" in r.text


def test_jobs_list_and_filters(client):
    r = client.get("/jobs")
    assert r.status_code == 200
    r2 = client.get("/jobs", params={"q": "python", "fresher": "1"})
    assert r2.status_code == 200


def test_job_detail_200_and_404(client):
    r = client.get("/api/jobs/latest?per_page=5")
    items = r.json()["items"]
    assert items, "seeded demo jobs must exist"
    job_id = items[0]["job_id"]
    detail = client.get(f"/jobs/{job_id}")
    assert detail.status_code == 200
    assert "APPLY DIRECTLY" in detail.text
    assert client.get("/jobs/999999").status_code == 404


def test_literal_routes_not_captured_as_job_id(client):
    assert client.get("/jobs/freshers").status_code == 200
    assert client.get("/jobs/search").status_code == 200
    assert client.get("/jobs/pune").status_code == 200
    assert client.get("/jobs/pune/freshers").status_code == 200
    assert client.get("/jobs/pune/cybersecurity").status_code == 200
    assert client.get("/jobs/pune/nonexistent-topic").status_code == 404


def test_demo_job_apply_shows_interstitial_never_redirects(client):
    # Seeded jobs are all demo — apply must NOT redirect anywhere.
    r = client.get("/api/jobs/latest?per_page=5")
    items = r.json()["items"]
    assert items, "seeded demo jobs must exist"
    job_id = items[0]["job_id"]
    resp = client.get(f"/apply/{job_id}", follow_redirects=False)
    assert resp.status_code == 200
    assert "demo" in resp.text.lower()
    assert "location" not in {k.lower() for k in resp.headers}


def test_apply_closed_returns_410(client):
    from app.core import database as db
    row = db.query_one("SELECT job_id FROM jobs WHERE job_status='expired' LIMIT 1")
    if row:
        db.execute("UPDATE jobs SET is_demo=0 WHERE job_id=?", (row["job_id"],))
        resp = client.get(f"/apply/{row['job_id']}", follow_redirects=False)
        assert resp.status_code == 410


def test_apply_real_job_redirects_to_application_url(client):
    from app.core import database as db
    db.execute(
        """UPDATE jobs SET is_demo=0, application_url='https://careers.example.com/apply/42'
           WHERE job_id = (SELECT MIN(job_id) FROM jobs)""")
    job_id = db.query_one("SELECT MIN(job_id) AS m FROM jobs")["m"]
    resp = client.get(f"/apply/{job_id}", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "https://careers.example.com/apply/42"
    # click tracked
    count = db.query_one("SELECT COUNT(*) AS c FROM application_clicks WHERE job_id=?", (job_id,))
    assert count["c"] >= 1


def test_qr_endpoints(client):
    r = client.get("/api/jobs/latest?per_page=5")
    items = r.json()["items"]
    assert items, "seeded demo jobs must exist"
    job_id = items[0]["job_id"]
    svg = client.get(f"/jobs/{job_id}/qr")
    assert svg.status_code == 200 and b"svg" in svg.headers["content-type"].encode()
    png = client.get(f"/jobs/{job_id}/qr?format=png")
    assert png.status_code == 200 and png.headers["content-type"] == "image/png"


def test_whatsapp_json_and_page(client):
    r = client.get("/api/jobs/latest?per_page=5")
    items = r.json()["items"]
    assert items, "seeded demo jobs must exist"
    job_id = items[0]["job_id"]
    j = client.get(f"/jobs/{job_id}/whatsapp?format=json").json()
    assert "Apply Directly" in j["text"]
    page = client.get(f"/jobs/{job_id}/whatsapp")
    assert page.status_code == 200 and "WhatsApp" in page.text


def test_stats_never_count_demo_rows(client):
    from app.core import database as db
    expected = int(db.query_one(
        "SELECT COUNT(*) AS c FROM jobs WHERE job_status='active' "
        "AND verification_status='approved' AND is_demo=0")["c"])
    data = client.get("/api/stats").json()
    assert data["total_active_jobs"] == expected  # demo rows never counted
    radar = client.get("/api/placement-radar").json()
    assert radar["totals"]["total"] == expected


def test_api_jobs_and_errors(client):
    assert client.get("/api/jobs").status_code == 200
    assert client.get("/api/jobs/999999").status_code == 404
    assert client.get("/api/domains").status_code == 200
    assert client.get("/api/skills").status_code == 200
    assert client.get("/api/companies").status_code == 200


def test_sitemap_and_robots(client):
    s = client.get("/sitemap.xml")
    assert s.status_code == 200 and "urlset" in s.text
    assert "/apply/" not in s.text
    r = client.get("/robots.txt")
    assert "Disallow: /apply/" in r.text


def test_admin_requires_login(client):
    r = client.get("/admin", follow_redirects=False)
    assert r.status_code in (303, 401)


def test_admin_login_and_review_flow(admin_client):
    r = admin_client.get("/admin")
    assert r.status_code == 200 and "Placement Intelligence" in r.text
    # CSRF: action without token must fail
    deny = admin_client.post("/admin/jobs/1/approve", data={}, follow_redirects=False)
    assert deny.status_code == 403
    # find a pending job + csrf token
    from app.core import database as db
    db.execute("""UPDATE jobs SET verification_status='needs_review'
                  WHERE job_id = (SELECT MIN(job_id) FROM jobs WHERE job_status='active')""")
    token = db.query_one("SELECT csrf_token FROM sessions LIMIT 1")["csrf_token"]
    job_id = db.query_one(
        "SELECT job_id FROM jobs WHERE verification_status='needs_review' LIMIT 1")["job_id"]
    ok = admin_client.post(f"/admin/jobs/{job_id}/approve",
                           data={"_csrf": token}, follow_redirects=False)
    assert ok.status_code == 303
    assert db.query_one("SELECT verification_status FROM jobs WHERE job_id=?", (job_id,))[
        "verification_status"] == "approved"


def test_admin_wrong_password_rejected(client):
    r = client.post("/admin/login", data={"email": "admin@skillected.local",
                                          "password": "wrong"})
    assert r.status_code == 401


def test_report_job_requires_csrf(client):
    from app.core import database as db
    job_id = db.query_one("SELECT MIN(job_id) AS m FROM jobs")["m"]
    deny = client.post(f"/jobs/{job_id}/report", data={"report_type": "incorrect"},
                       follow_redirects=False)
    assert deny.status_code == 403
