import pytest
from httpx import AsyncClient

from app.providers.apify import ApifyLeadDiscoveryProvider
from app.providers.apollo import ApolloProvider
from app.providers.google_sheets import GoogleSheetsProvider


@pytest.mark.asyncio
async def test_mock_apify_provider():
    provider = ApifyLeadDiscoveryProvider(mock_mode=True)
    records = await provider.search_businesses(locations=["KGF"], categories=["restaurants"], limit=5)

    assert len(records) > 0
    for r in records:
        assert r.business_name
        # Verify strict factual rules: if website is empty, it MUST be None, never placeholder
        if not r.website:
            assert r.website is None
        if not r.phone:
            assert r.phone is None
        if not r.email:
            assert r.email is None


@pytest.mark.asyncio
async def test_mock_apollo_provider():
    provider = ApolloProvider(mock_mode=True)
    res = await provider.enrich_business(business_name="Kolar Gold Tech Solutions", domain="kolargoldtech.in")

    assert res.found is True
    assert len(res.contacts) >= 1
    contact = res.contacts[0]
    assert contact.name == "Ramesh Kumar"
    assert "kolargoldtech.in" in contact.email
    assert contact.is_verified is True


@pytest.mark.asyncio
async def test_google_sheets_null_handling():
    provider = GoogleSheetsProvider(mock_mode=True)
    lead_with_missing_fields = {
        "business_name": "Sri Krishna Grand Hotel",
        "owner_name": None,
        "email": None,
        "phone": "+918153255678",
        "city": "Bangarapet",
        "website": None,  # MUST be empty string in sheet!
        "category": "hotels",
        "lead_score": 65,
        "opportunity": "NO_WEBSITE",
        "status": "NEW",
        "source": "apify",
        "created_at": "2026-10-05T12:00:00Z",
    }
    row = provider._format_lead_row(lead_with_missing_fields)
    # Columns: [Business Name, Owner Name, Email, Phone, Location, Website, Category, Lead Score, Opportunity, Lead Status, Source, Created At]
    assert row[0] == "Sri Krishna Grand Hotel"
    assert row[1] == ""  # Owner Name must be blank string, never 'None' or 'N/A'
    assert row[2] == ""  # Email must be blank string
    assert row[3] == "+918153255678"
    assert row[4] == "Bangarapet"
    assert row[5] == ""  # Website must be blank string, never 'None' or 'N/A'


@pytest.mark.asyncio
async def test_provider_status_endpoint(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/providers/status", headers=auth_headers)
    assert resp.status_code == 200
    providers = resp.json()["providers"]
    provider_names = {p["provider"] for p in providers}
    assert "apify" in provider_names
    assert "apollo" in provider_names
    assert "openrouter" in provider_names
    assert "google_sheets" in provider_names
