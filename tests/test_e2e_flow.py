import asyncio
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.business import Business
from app.db.models.campaign import Campaign, CampaignLead
from app.db.models.google_sheet import GoogleSheetExport
from app.db.models.job import DiscoveryJob
from app.db.models.lead_score import LeadScore
from app.db.models.ai_decision import AIDecision
from app.db.models.outreach import OutreachStatus
from app.providers.google_sheets import GoogleSheetsProvider
from app.workers.discovery_tasks import _run_campaign_discovery


@pytest.mark.asyncio
async def test_full_lead_generation_e2e_flow(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """
    Complete end-to-end integration test:
    1. Create campaign via REST API
    2. Start campaign execution
    3. Run full discovery pipeline (Apify mock -> Normalization -> Deduplication -> Storage)
    4. Run enrichment (Website inspection + Apollo contact enrichment)
    5. Run Jev AI qualification & opportunity detection
    6. Compute hybrid deterministic + AI lead scores
    7. Export to Google Sheets mock destination
    8. Assert data fidelity:
       - Factual fields only
       - Missing websites remain NULL / empty
       - No hallucinated data
    """

    # 1. Create Campaign
    create_payload = {
        "name": "KGF & Bangarapet Business Lead Discovery",
        "description": "High-priority outreach for website modernization and new web development",
        "locations": ["KGF", "Bangarapet"],
        "categories": ["restaurants", "retail", "hotels", "clinics"],
        "max_leads": 10,
        "enrich_contacts": True,
        "analyze_websites": False,
        "ai_qualification": True,
        "google_sheet_sync": True,
        "max_apollo_credits": 10,
        "max_ai_requests": 10,
    }
    create_resp = await client.post("/api/v1/campaigns", headers=auth_headers, json=create_payload)
    assert create_resp.status_code == 201
    campaign_data = create_resp.json()
    campaign_id = campaign_data["id"]

    # 2. Trigger Campaign Run via REST API (Mock Celery task queue dispatch in unit test)
    from unittest.mock import patch, MagicMock
    with patch("app.workers.discovery_tasks.discover_campaign_leads.delay") as mock_delay:
        mock_delay.return_value = MagicMock(id="mock-task-id-123")
        run_resp = await client.post(f"/api/v1/campaigns/{campaign_id}/run", headers=auth_headers)
        assert run_resp.status_code == 200
        run_data = run_resp.json()
        job_id = run_data["job_id"]
        assert job_id is not None

    # 3. Execute the full background pipeline directly using db_session
    # (Since in-memory SQLite fixture is used for test isolation)
    await _run_campaign_discovery(job_id, campaign_id, session=db_session)

    # 4. Verify Job completed
    job_stmt = select(DiscoveryJob).where(DiscoveryJob.id == job_id)
    job_res = await db_session.execute(job_stmt)
    job = job_res.scalars().first()
    assert job is not None
    assert job.status == "completed"
    assert job.progress == 100
    assert job.successful > 0

    # 5. Verify Campaign status and associations
    camp_stmt = select(Campaign).where(Campaign.id == campaign_id)
    camp_res = await db_session.execute(camp_stmt)
    campaign = camp_res.scalars().first()
    assert campaign.status == "COMPLETED"
    assert campaign.leads_discovered > 0

    # 6. Verify Stored Leads
    lead_ids_stmt = select(CampaignLead.business_id).where(CampaignLead.campaign_id == campaign_id)
    lead_ids_res = await db_session.execute(lead_ids_stmt)
    lead_ids = lead_ids_res.scalars().all()
    assert len(lead_ids) > 0

    leads_stmt = (
        select(Business)
        .where(Business.id.in_(lead_ids))
        .options(
            selectinload(Business.scores),
            selectinload(Business.ai_decisions),
            selectinload(Business.contacts),
            selectinload(Business.outreach),
        )
    )
    leads_res = await db_session.execute(leads_stmt)
    leads = leads_res.scalars().all()

    found_no_website_lead = False
    found_website_lead = False

    for lead in leads:
        assert lead.business_name
        assert lead.source == "apify"

        # Check scores
        assert len(lead.scores) > 0
        final_score = lead.scores[0].final_score
        assert 0 <= final_score <= 100

        # Check AI decision
        assert len(lead.ai_decisions) > 0
        decision = lead.ai_decisions[0]
        assert decision.opportunity in [
            "NO_WEBSITE",
            "WEBSITE_REBUILD",
            "ECOMMERCE_OPPORTUNITY",
            "WEBSITE_SECURITY",
            "UNKNOWN",
        ]

        # Check Outreach status
        assert lead.outreach is not None
        assert lead.outreach.status == "NEW"

        # Check strict factual contact rule:
        # If website is missing, it MUST be None, NOT "N/A" or "None"
        if not lead.has_website:
            found_no_website_lead = True
            assert lead.website is None
            assert decision.opportunity == "NO_WEBSITE"
        else:
            found_website_lead = True
            assert lead.website.startswith("http")

    assert found_no_website_lead, "Pipeline must discover leads without websites"
    assert found_website_lead, "Pipeline must discover leads with websites"

    # 7. Verify Google Sheets export record
    sheet_stmt = select(GoogleSheetExport).where(GoogleSheetExport.campaign_id == campaign_id)
    sheet_res = await db_session.execute(sheet_stmt)
    sheet_export = sheet_res.scalars().first()
    assert sheet_export is not None
    assert sheet_export.status == "completed"
    assert sheet_export.total_rows_exported == len(leads)

    # 8. Verify Google Sheets Row Format null rules
    sheets_provider = GoogleSheetsProvider(mock_mode=True)
    sample_lead = next(l for l in leads if not l.has_website)
    sheet_row = sheets_provider._format_lead_row({
        "business_name": sample_lead.business_name,
        "owner_name": sample_lead.owner_name,
        "email": sample_lead.email,
        "phone": sample_lead.phone,
        "city": sample_lead.city,
        "website": sample_lead.website,
        "category": sample_lead.category,
        "lead_score": sample_lead.scores[0].final_score,
        "opportunity": sample_lead.ai_decisions[0].opportunity,
        "status": sample_lead.outreach.status,
        "source": sample_lead.source,
        "created_at": sample_lead.created_at,
    })
    # Website cell (index 5) MUST be empty string ""
    assert sheet_row[5] == ""
