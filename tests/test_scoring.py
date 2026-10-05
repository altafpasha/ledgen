import pytest
from app.db.models.business import Business
from app.db.models.website_analysis import WebsiteAnalysis
from app.services.scoring_service import ScoringService


def test_scoring_no_website():
    business = Business(
        business_name="Bangarapet Grand Hotel",
        category="hotels",
        city="Bangarapet",
        state="Karnataka",
        phone="+919845012345",
        email=None,
        website=None,
        has_website=False,
    )
    score, breakdown = ScoringService.calculate_deterministic_score(business)
    # 40 (no website) + 10 (phone) + 10 (hotel category) + 5 (Bangarapet location) = 65
    assert score == 65
    assert breakdown.get("no_website") == 40
    assert breakdown.get("valid_phone") == 10
    assert breakdown.get("target_category") == 10
    assert breakdown.get("priority_location") == 5


def test_scoring_with_insecure_website():
    business = Business(
        business_name="Kolar Silk Sarees",
        category="retail",
        city="Kolar",
        state="Karnataka",
        phone="+918152223456",
        email="orders@kolarsilks.com",
        website="http://kolarsilks.com",
        has_website=True,
    )
    analysis = WebsiteAnalysis(
        website_url="http://kolarsilks.com",
        is_https=False,
        http_status=200,
        performance_indicators={"is_slow": True, "missing_viewport": True},
    )
    score, breakdown = ScoringService.calculate_deterministic_score(business, analysis)
    # 15 (insecure/HTTP) + 10 (slow) + 10 (mobile missing) + 10 (phone) + 10 (email) + 10 (retail) + 5 (Kolar) = 70
    assert score == 70
    assert breakdown.get("insecure_or_broken_website") == 15
    assert breakdown.get("poor_performance") == 10


def test_hybrid_final_score():
    det_score = 70
    ai_score = 90
    final = ScoringService.compute_final_score(det_score, ai_score)
    # round(0.55 * 70 + 0.45 * 90) = round(38.5 + 40.5) = 79
    assert final == 79
