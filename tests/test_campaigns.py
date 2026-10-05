import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_campaign_crud(client: AsyncClient, auth_headers: dict):
    # 1. Create Campaign
    payload = {
        "name": "KGF Restaurant Web Development",
        "description": "Targeting local restaurants and cafes without website",
        "locations": ["KGF", "Bangarapet"],
        "categories": ["restaurants", "hotels"],
        "max_leads": 100,
        "enrich_contacts": True,
        "analyze_websites": True,
        "ai_qualification": True,
        "google_sheet_sync": True,
    }
    create_resp = await client.post("/api/v1/campaigns", headers=auth_headers, json=payload)
    assert create_resp.status_code == 201
    camp = create_resp.json()
    campaign_id = camp["id"]
    assert camp["name"] == payload["name"]
    assert camp["status"] == "DRAFT"

    # 2. Get Campaign
    get_resp = await client.get(f"/api/v1/campaigns/{campaign_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == campaign_id

    # 3. Update Campaign
    patch_resp = await client.patch(
        f"/api/v1/campaigns/{campaign_id}",
        headers=auth_headers,
        json={"name": "Updated KGF Campaign", "max_leads": 200},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Updated KGF Campaign"
    assert patch_resp.json()["max_leads"] == 200

    # 4. List Campaigns
    list_resp = await client.get("/api/v1/campaigns", headers=auth_headers)
    assert list_resp.status_code == 200
    paged = list_resp.json()
    assert paged["total"] >= 1
    assert len(paged["items"]) >= 1

    # 5. Pause & Resume Campaign
    pause_resp = await client.post(f"/api/v1/campaigns/{campaign_id}/pause", headers=auth_headers)
    assert pause_resp.status_code == 200
    assert pause_resp.json()["status"] == "PAUSED"

    resume_resp = await client.post(f"/api/v1/campaigns/{campaign_id}/resume", headers=auth_headers)
    assert resume_resp.status_code == 200
    assert resume_resp.json()["status"] == "QUEUED"

    # 6. Campaign Stats
    stats_resp = await client.get(f"/api/v1/campaigns/{campaign_id}/stats", headers=auth_headers)
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert "total_leads" in stats
    assert "average_score" in stats
