from app.services import scoring


def test_authenticity_official_https_high():
    job = {"source_type": "official_careers", "application_url": "https://careers.x.com/apply/1",
           "official_company_url": "https://x.com", "job_requisition_id": "R-1",
           "posting_date": "2026-09-08", "posting_date_verified": 1,
           "last_verified_at": "2026-09-08 10:00:00", "verification_status": "approved",
           "job_title": "Engineer", "job_description": "Build things", "company_name": "X"}
    score, flags = scoring.authenticity_score(job, source_reliability=95)
    assert score >= 85 and not flags


def test_authenticity_payment_request_penalized():
    job = {"source_type": "official_careers", "application_url": "https://x.com/apply",
           "job_title": "Engineer", "job_description": "Pay registration fee to apply",
           "company_name": "X", "verification_status": "pending"}
    score, flags = scoring.authenticity_score(job)
    assert "payment_request" in flags


def test_authenticity_aggregator_penalized():
    job = {"source_type": "official_careers",
           "application_url": "https://www.naukri.com/job/123",
           "job_title": "Engineer", "company_name": "X", "verification_status": "pending"}
    score, flags = scoring.authenticity_score(job)
    assert "aggregator_application_url" in flags


def test_missing_application_url_flagged():
    job = {"source_type": "official_careers", "application_url": "",
           "job_title": "E", "company_name": "X", "verification_status": "pending"}
    score, flags = scoring.authenticity_score(job)
    assert "missing_application_url" in flags


def test_publish_thresholds_default():
    assert scoring.publish_decision(90) == "auto_publish"
    assert scoring.publish_decision(75) == "manual_review"
    assert scoring.publish_decision(60) == "reject"


def test_source_reliability_tiers():
    assert scoring.source_reliability({"source_type": "official_careers", "error_count": 0}) > 90
    assert scoring.source_reliability({"source_type": "official_ats", "ats_type": "greenhouse"}) >= 85
    assert scoring.source_reliability({"source_type": "permitted_public"}) < 70


def test_source_reliability_error_penalty_and_override():
    base = scoring.source_reliability({"source_type": "official_careers", "error_count": 5})
    assert base < 95
    assert scoring.source_reliability({"source_type": "official_careers", "reliability_override": 70}) == 70


def test_duplicate_hash_stable_and_sensitive():
    a = scoring.duplicate_hash("Persistent", "software engineer", "Pune", "R1", "https://x/a")
    b = scoring.duplicate_hash("persistent ", "Software  Engineer", "pune", "r1", "https://x/a")
    assert a == b
    c = scoring.duplicate_hash("Persistent", "software engineer", "Pune", "R2", "https://x/a")
    assert a != c


def test_opportunity_score_bands():
    job = {"job_status": "active", "authenticity_score": 95}
    score, band, _ = scoring.opportunity_score(job, 20, True, 80, True)
    assert score >= 70 and "HIGH" in band
    score2, band2, _ = scoring.opportunity_score({"job_status": "active"}, 2000, False, 0, False)
    assert score2 < 70


def test_opportunity_never_mentions_applicants():
    _, band, reasons = scoring.opportunity_score({"job_status": "active"}, 10, True, 90, True)
    blob = (band + " ".join(reasons)).lower()
    assert "applicant" not in blob
