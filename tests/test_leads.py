import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.business import Business
from app.db.models.lead_score import LeadScore
from app.db.models.outreach import OutreachStatus


@pytest.mark.asyncio
async def test_leads_query_and_crm(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    # 1. Insert test leads directly
    lead1 = Business(
        business_name="Robertsonpet Bakery",
        city="KGF",
        category="retail",
        phone="+919845011111",
        email=None,
        website=None,
        has_website=False,
        source="apify",
    )
    lead2 = Business(
        business_name="Bangarapet Grand Tech",
        city="Bangarapet",
        category="software",
        phone="+919845022222",
        email="tech@bangarapet.in",
        website="https://bangarapet.in",
        has_website=True,
        source="apify",
    )
    db_session.add_all([lead1, lead2])
    await db_session.flush()

    db_session.add(LeadScore(business_id=lead1.id, deterministic_score=80, final_score=80))
    db_session.add(LeadScore(business_id=lead2.id, deterministic_score=60, final_score=60))
    db_session.add(OutreachStatus(business_id=lead1.id, status="NEW"))
    db_session.add(OutreachStatus(business_id=lead2.id, status="NEW"))
    await db_session.commit()

    # 2. Query all leads
    resp = await client.get("/api/v1/leads", headers=auth_headers)
    assert resp.status_code == 200
    paged = resp.json()
    assert paged["total"] == 2

    # 3. Filter by has_website=false
    no_web_resp = await client.get("/api/v1/leads?has_website=false", headers=auth_headers)
    assert no_web_resp.status_code == 200
    items = no_web_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["business_name"] == "Robertsonpet Bakery"
    assert items[0]["website"] is None

    # 4. Filter by location
    bpt_resp = await client.get("/api/v1/leads?location=Bangarapet", headers=auth_headers)
    assert bpt_resp.status_code == 200
    assert len(bpt_resp.json()["items"]) == 1
    assert bpt_resp.json()["items"][0]["business_name"] == "Bangarapet Grand Tech"

    # 5. Mark lead1 as Contacted
    contact_resp = await client.post(f"/api/v1/leads/{lead1.id}/contacted", headers=auth_headers)
    assert contact_resp.status_code == 200
    assert contact_resp.json()["status"] == "CONTACTED"
    assert contact_resp.json()["last_contacted_at"] is not None

    # 6. Add notes
    notes_resp = await client.post(
        f"/api/v1/leads/{lead1.id}/notes",
        headers=auth_headers,
        json={"contact_notes": "Spoke with owner, interested in a 5-page responsive website."},
    )
    assert notes_resp.status_code == 200
    assert "5-page responsive website" in notes_resp.json()["contact_notes"]
