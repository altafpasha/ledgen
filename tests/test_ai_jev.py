import pytest
from app.ai.jev import JevIntelligenceLayer
from app.ai.schemas import JevDecisionSchema
from app.db.models.business import Business
from app.db.models.website_analysis import WebsiteAnalysis


@pytest.mark.asyncio
async def test_jev_mock_qualification_no_website():
    jev = JevIntelligenceLayer(mock_mode=True)
    business = Business(
        business_name="Bangarapet Sri Krishna Grand Hotel",
        phone="+918153255678",
        website=None,
        has_website=False,
        category="hotels",
        city="Bangarapet",
    )
    decision = await jev.qualify_lead(business)

    assert isinstance(decision, JevDecisionSchema)
    assert decision.opportunity == "NO_WEBSITE"
    assert decision.recommended_service == "website_development"
    assert decision.lead_quality == "high"
    assert decision.needs_enrichment is True
    assert decision.confidence >= 0.8


@pytest.mark.asyncio
async def test_jev_mock_qualification_security_opportunity():
    jev = JevIntelligenceLayer(mock_mode=True)
    business = Business(
        business_name="Kolar Silk Sarees",
        website="http://kolarsilks.com",
        has_website=True,
        category="retail",
        city="Kolar",
    )
    analysis = WebsiteAnalysis(
        website_url="http://kolarsilks.com",
        is_https=False,
        http_status=200,
    )
    decision = await jev.qualify_lead(business, website_analysis=analysis)

    assert isinstance(decision, JevDecisionSchema)
    assert decision.opportunity == "WEBSITE_SECURITY"
    assert decision.recommended_service == "website_security"
