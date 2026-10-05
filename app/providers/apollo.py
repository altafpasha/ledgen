import json
import os
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings
from app.core.exceptions import ProviderException
from app.core.logging import logger
from app.providers.base import ContactEnrichmentProvider, ContactPerson, EnrichmentResult
from app.utils.email import normalize_email
from app.utils.phone import normalize_phone


class ApolloProvider(ContactEnrichmentProvider):
    """
    Apollo.io Provider for contact and organization enrichment.
    Handles rate limits, credit exhaustion, and missing data gracefully.
    """

    def __init__(self, api_key: Optional[str] = None, mock_mode: Optional[bool] = None):
        self.api_key = api_key or settings.apollo_api_key
        self.mock_mode = mock_mode if mock_mode is not None else settings.mock_providers

    async def enrich_business(
        self,
        business_name: str,
        domain: Optional[str] = None,
        location: Optional[str] = None,
        **kwargs
    ) -> EnrichmentResult:
        """
        Enriches a business record with executive / owner contact information.
        """
        if self.mock_mode or not self.api_key:
            logger.info("Using Mock Apollo Provider", extra={"event": "apollo_mock_enrichment"})
            return self._mock_enrichment(business_name, domain)

        return await self._live_enrichment(business_name, domain, location)

    def _mock_enrichment(self, business_name: str, domain: Optional[str]) -> EnrichmentResult:
        fixture_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "fixtures",
            "apollo_mock.json"
        )

        if not os.path.exists(fixture_path):
            return EnrichmentResult(found=False, credits_used=0.0, status="not_found")

        with open(fixture_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        target_entry = None
        if domain and domain in data:
            target_entry = data[domain]
        else:
            # Check by business name matching
            for dom, item in data.items():
                org_name = (item.get("organization") or {}).get("name", "").lower()
                if org_name and (org_name in business_name.lower() or business_name.lower() in org_name):
                    target_entry = item
                    break

        if not target_entry:
            return EnrichmentResult(found=False, credits_used=0.0, status="not_found")

        contacts: List[ContactPerson] = []
        for p in target_entry.get("people", []):
            email = normalize_email(p.get("email"))
            phone = normalize_phone(p.get("phone"))
            contacts.append(
                ContactPerson(
                    name=p.get("name"),
                    title=p.get("title"),
                    email=email,
                    phone=phone,
                    linkedin_url=p.get("linkedin_url"),
                    is_verified=(p.get("email_status") == "verified"),
                )
            )

        return EnrichmentResult(
            found=True,
            contacts=contacts,
            company_details=target_entry.get("organization"),
            credits_used=1.0,
            status="success",
        )

    async def _live_enrichment(
        self,
        business_name: str,
        domain: Optional[str],
        location: Optional[str]
    ) -> EnrichmentResult:
        url = "https://api.apollo.io/v1/people/match"
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": self.api_key or "",
        }

        payload: Dict[str, Any] = {
            "organization_name": business_name,
        }
        if domain:
            payload["domain"] = domain

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, headers=headers, json=payload)

                if resp.status_code == 429:
                    logger.warning("Apollo rate limit hit", extra={"event": "apollo_rate_limit"})
                    return EnrichmentResult(found=False, credits_used=0.0, status="rate_limited")

                if resp.status_code == 402:
                    logger.warning("Apollo credits exhausted", extra={"event": "apollo_credit_exhausted"})
                    return EnrichmentResult(found=False, credits_used=0.0, status="credits_exhausted")

                if resp.status_code != 200:
                    logger.error(f"Apollo API error {resp.status_code}: {resp.text[:200]}")
                    return EnrichmentResult(found=False, credits_used=0.0, status="api_error")

                data = resp.json()
                person = data.get("person")
                if not person:
                    return EnrichmentResult(found=False, credits_used=0.0, status="not_found")

                name = person.get("name")
                email = normalize_email(person.get("email"))
                phone = normalize_phone(person.get("phone_numbers", [{}])[0].get("raw_number") if person.get("phone_numbers") else None)

                contact = ContactPerson(
                    name=name,
                    title=person.get("title"),
                    email=email,
                    phone=phone,
                    linkedin_url=person.get("linkedin_url"),
                    is_verified=(person.get("email_status") == "verified"),
                )

                return EnrichmentResult(
                    found=True,
                    contacts=[contact],
                    company_details=person.get("organization"),
                    credits_used=1.0,
                    status="success",
                    raw_response=data,
                )

        except httpx.RequestError as e:
            logger.error(f"Apollo connection error: {str(e)}")
            return EnrichmentResult(found=False, credits_used=0.0, status="network_error")
