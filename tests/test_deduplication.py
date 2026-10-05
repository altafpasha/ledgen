import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.business import Business
from app.providers.base import BusinessRecord
from app.services.deduplication_service import DeduplicationService


@pytest.mark.asyncio
async def test_deduplication_tiers(db_session: AsyncSession):
    # Existing business
    original = Business(
        business_name="Kolar Gold Tech Solutions Pvt Ltd",
        normalized_business_name="kolar gold tech",
        phone="+919845012345",
        normalized_phone="+919845012345",
        email="contact@kolargoldtech.in",
        website="https://kolargoldtech.in",
        website_domain="kolargoldtech.in",
        has_website=True,
        city="KGF",
        address="Robertsonpet Main Road",
        source="apify",
        source_business_id="apify_kgf_001",
    )
    db_session.add(original)
    await db_session.commit()

    # Priority 1: Match by source + source_business_id
    rec1 = BusinessRecord(
        business_name="Different Name",
        source="apify",
        source_business_id="apify_kgf_001",
    )
    match1 = await DeduplicationService.find_duplicate(db_session, rec1)
    assert match1 is not None
    assert match1.id == original.id

    # Priority 2: Match by normalized phone
    rec2 = BusinessRecord(
        business_name="Completely New Name",
        phone="+919845012345",
    )
    match2 = await DeduplicationService.find_duplicate(db_session, rec2)
    assert match2 is not None
    assert match2.id == original.id

    # Priority 3: Match by confirmed domain
    rec3 = BusinessRecord(
        business_name="Another Variant",
        website="https://www.kolargoldtech.in/contact",
    )
    match3 = await DeduplicationService.find_duplicate(db_session, rec3)
    assert match3 is not None
    assert match3.id == original.id

    # Non-duplicate: Distinct business
    rec_distinct = BusinessRecord(
        business_name="Different Shop in KGF",
        city="KGF",
        phone="+919888877777",
        website="https://differentshop.com",
    )
    match_distinct = await DeduplicationService.find_duplicate(db_session, rec_distinct)
    assert match_distinct is None
