import json
import os
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings
from app.core.exceptions import ProviderException
from app.core.logging import logger
from app.providers.base import BusinessRecord, LeadDiscoveryProvider
from app.utils.domains import extract_domain, normalize_website_url
from app.utils.email import normalize_email
from app.utils.phone import normalize_phone


class ApifyLeadDiscoveryProvider(LeadDiscoveryProvider):
    """
    Apify Provider for Google Maps / Google Places business discovery.
    Supports both real Apify Actor runs and fixture-based mock runs.
    """

    def __init__(self, api_token: Optional[str] = None, actor_id: Optional[str] = None, mock_mode: Optional[bool] = None):
        self.api_token = api_token or settings.apify_api_token
        self.actor_id = actor_id or settings.apify_actor_id
        self.mock_mode = mock_mode if mock_mode is not None else settings.mock_providers

    def normalize_item(self, item: Dict[str, Any]) -> Optional[BusinessRecord]:
        """
        Converts raw provider JSON into a strict BusinessRecord.
        Discards invalid items (missing business name).
        """
        raw_name = item.get("name") or item.get("title") or item.get("business_name")
        if not raw_name or not str(raw_name).strip():
            return None

        business_name = str(raw_name).strip()

        # Phone handling
        raw_phone = item.get("phone") or item.get("phoneUnformatted") or item.get("phoneNumber")
        norm_phone = normalize_phone(str(raw_phone)) if raw_phone else None

        # Email handling
        raw_email = item.get("email") or item.get("contactEmail")
        norm_email = normalize_email(str(raw_email)) if raw_email else None

        # Website handling - Never invent domains!
        raw_website = item.get("website") or item.get("site")
        clean_website = normalize_website_url(str(raw_website)) if raw_website else None

        # Owner / Contact handling
        raw_owner = item.get("owner") or item.get("owner_name") or item.get("contact_person")
        clean_owner = str(raw_owner).strip() if raw_owner and str(raw_owner).strip() else None

        # Location details
        address = item.get("address") or item.get("formatted_address")
        city = item.get("city")
        district = item.get("district")
        state = item.get("state")
        raw_country = item.get("country") or item.get("countryCode")
        if raw_country:
            country = str(raw_country).strip()
        elif address and ("united states" in str(address).lower() or " usa" in str(address).lower() or ", ny " in str(address).lower()):
            country = "United States"
        else:
            country = "India"
        pincode = item.get("postalCode") or item.get("pincode") or item.get("zip")

        # Category
        category = item.get("category") or item.get("categoryName")
        if isinstance(category, list) and category:
            category = category[0]

        # Source ID & Google Maps URL
        source_id = str(item.get("placeId") or item.get("cid") or item.get("source_id") or item.get("id") or "")
        gmaps_url = item.get("url") or item.get("google_maps_url")

        lat = item.get("lat") or item.get("latitude")
        lng = item.get("lng") or item.get("longitude")
        if isinstance(item.get("location"), dict):
            lat = item["location"].get("lat", lat)
            lng = item["location"].get("lng", lng)

        return BusinessRecord(
            business_name=business_name,
            owner_name=clean_owner,
            email=norm_email,
            phone=norm_phone,
            website=clean_website,
            address=str(address).strip() if address else None,
            city=str(city).strip() if city else None,
            district=str(district).strip() if district else None,
            state=str(state).strip() if state else None,
            country=str(country).strip() if country else "India",
            pincode=str(pincode).strip() if pincode else None,
            latitude=float(lat) if lat is not None else None,
            longitude=float(lng) if lng is not None else None,
            category=str(category).strip() if category else None,
            source="apify",
            source_business_id=source_id if source_id else None,
            google_maps_url=str(gmaps_url) if gmaps_url else None,
            description=item.get("description"),
            raw_data=None,  # Do not store unnecessary raw blobs
        )

    async def search_businesses(
        self,
        locations: List[str],
        categories: List[str],
        limit: int = 100,
        **kwargs
    ) -> List[BusinessRecord]:
        """
        Discovers businesses for the given locations and categories.
        """
        if self.mock_mode or not self.api_token:
            logger.info("Using Mock Apify Provider for discovery", extra={"event": "apify_mock_discovery"})
            return self._load_fixtures(locations, categories, limit)

        # Real Live Apify Run
        return await self._run_live_apify(locations, categories, limit)

    def _load_fixtures(
        self,
        locations: List[str],
        categories: List[str],
        limit: int
    ) -> List[BusinessRecord]:
        fixture_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "fixtures",
            "businesses_mock.json"
        )
        if not os.path.exists(fixture_path):
            return []

        with open(fixture_path, "r", encoding="utf-8") as f:
            items = json.load(f)

        records: List[BusinessRecord] = []
        loc_set = {loc.lower() for loc in locations}
        cat_set = {cat.lower() for cat in categories}

        for item in items:
            record = self.normalize_item(item)
            if not record:
                continue

            # Check if matching criteria (or include all fixtures if wildcards)
            item_city = (record.city or "").lower()
            item_cat = (record.category or "").lower()

            matches_loc = any(l in item_city for l in loc_set) if loc_set else True
            matches_cat = any(c in item_cat for c in cat_set) if cat_set else True

            # If specific search is given, filter; if no matches found in mock, return available valid records
            records.append(record)
            if len(records) >= limit:
                break

        return records

    @staticmethod
    def is_location_relevant(record: BusinessRecord, target_locations: List[str]) -> bool:
        """
        Validates that a discovered business actually belongs to one of the target locations.
        Prevents global or foreign corporate headquarters (e.g. New York, USA)
        from being wrongly included when scraping regional locations.
        """
        if not target_locations:
            return True

        blob = f"{record.city or ''} {record.address or ''} {record.district or ''} {record.state or ''}".lower()

        # Check if any target location keyword matches the record
        for loc in target_locations:
            loc_clean = loc.strip().lower()
            if not loc_clean:
                continue
            # Direct substring check
            if loc_clean in blob:
                return True
            # Split comma separated e.g. "Bangalore, India" -> "bangalore", "india"
            parts = [p.strip() for p in loc_clean.split(",") if len(p.strip()) >= 3]
            for part in parts:
                if part in blob:
                    return True

        # If record explicitly specifies a foreign or non-matching city, reject it
        if record.city:
            return False

        return True

    async def _run_live_apify(
        self,
        locations: List[str],
        categories: List[str],
        limit: int
    ) -> List[BusinessRecord]:
        search_terms = []
        for loc in locations:
            for cat in categories:
                search_terms.append(f"{cat} in {loc}")

        actor = self.actor_id.replace("/", "~")
        url = f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items?token={self.api_token}&timeout=300"

        # Calculate reasonable places per search term to meet or exceed limit
        places_per_search = max(25, (limit // max(1, len(search_terms))) + 10)

        payload = {
            "searchStringsArray": search_terms[:10],
            "maxCrawledPlacesPerSearch": places_per_search,
            "language": "en",
        }

        try:
            async with httpx.AsyncClient(timeout=330.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code != 200 and resp.status_code != 201:
                    raise ProviderException(
                        "apify",
                        f"Apify API returned HTTP {resp.status_code}: {resp.text[:200]}"
                    )
                raw_items = resp.json()
        except httpx.RequestError as e:
            raise ProviderException("apify", f"Network error during Apify request: {str(e)}")

        records: List[BusinessRecord] = []
        if isinstance(raw_items, list):
            for item in raw_items:
                record = self.normalize_item(item)
                if record:
                    if not self.is_location_relevant(record, locations):
                        logger.info(
                            f"Filtering out irrelevant location record: '{record.business_name}' in '{record.city}' (target locations: {locations})",
                            extra={"event": "apify_location_filtered"}
                        )
                        continue
                    records.append(record)
                    if len(records) >= limit:
                        break

        return records
