import difflib
from typing import Optional
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.business import Business
from app.providers.base import BusinessRecord
from app.utils.domains import extract_domain
from app.utils.normalization import normalize_business_name, normalize_address


class DeduplicationService:
    """
    Implements multi-tier deduplication before inserting or updating business leads.
    Priority order:
    1. Provider business ID (source + source_business_id)
    2. Normalized phone
    3. Website domain
    4. Business name + address
    5. Business name + phone
    6. Controlled fuzzy matching on name + city
    """

    @staticmethod
    async def find_duplicate(session: AsyncSession, record: BusinessRecord) -> Optional[Business]:
        # Priority 1: Provider Business ID
        if record.source and record.source_business_id:
            stmt = select(Business).where(
                and_(
                    Business.source == record.source,
                    Business.source_business_id == record.source_business_id,
                )
            )
            res = await session.execute(stmt)
            existing = res.scalars().first()
            if existing:
                return existing

        # Priority 2: Normalized Phone Number
        if record.phone:
            stmt = select(Business).where(Business.normalized_phone == record.phone)
            res = await session.execute(stmt)
            existing = res.scalars().first()
            if existing:
                return existing

        # Priority 3: Website Domain (only when domain is confirmed)
        if record.website:
            domain = extract_domain(record.website)
            if domain:
                stmt = select(Business).where(Business.website_domain == domain)
                res = await session.execute(stmt)
                existing = res.scalars().first()
                if existing:
                    return existing

        norm_name = normalize_business_name(record.business_name)
        if not norm_name:
            return None

        # Priority 4: Business Name + Address
        if record.address:
            norm_addr = normalize_address(record.address)
            if norm_addr:
                stmt = select(Business).where(
                    and_(
                        Business.normalized_business_name == norm_name,
                        Business.city == record.city,
                    )
                )
                res = await session.execute(stmt)
                candidates = res.scalars().all()
                for c in candidates:
                    if c.address and norm_addr in normalize_address(c.address):
                        return c

        # Priority 5: Business Name + Phone
        if record.phone:
            stmt = select(Business).where(
                and_(
                    Business.normalized_business_name == norm_name,
                    Business.normalized_phone == record.phone,
                )
            )
            res = await session.execute(stmt)
            existing = res.scalars().first()
            if existing:
                return existing

        # Priority 6: Carefully controlled fuzzy matching (Name similarity > 0.92 within same city)
        if record.city:
            stmt = select(Business).where(Business.city == record.city)
            res = await session.execute(stmt)
            same_city_leads = res.scalars().all()
            for lead in same_city_leads:
                if not lead.normalized_business_name:
                    continue
                similarity = difflib.SequenceMatcher(
                    None,
                    norm_name,
                    lead.normalized_business_name
                ).ratio()
                if similarity >= 0.92:
                    # Require secondary match (category or location or partial address) to avoid false positives
                    if lead.category == record.category or (lead.pincode and lead.pincode == record.pincode):
                        return lead

        return None
