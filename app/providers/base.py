from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class BusinessRecord(BaseModel):
    business_name: str
    owner_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = "India"
    pincode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    source: str = "apify"
    source_business_id: Optional[str] = None
    google_maps_url: Optional[str] = None
    description: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None


class ContactPerson(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    is_verified: bool = False


class EnrichmentResult(BaseModel):
    found: bool
    contacts: List[ContactPerson] = []
    company_details: Optional[Dict[str, Any]] = None
    credits_used: float = 0.0
    status: str = "success"
    raw_response: Optional[Dict[str, Any]] = None


class LeadDiscoveryProvider(ABC):
    @abstractmethod
    async def search_businesses(
        self,
        locations: List[str],
        categories: List[str],
        limit: int,
        **kwargs
    ) -> List[BusinessRecord]:
        pass


class ContactEnrichmentProvider(ABC):
    @abstractmethod
    async def enrich_business(
        self,
        business_name: str,
        domain: Optional[str] = None,
        location: Optional[str] = None,
        **kwargs
    ) -> EnrichmentResult:
        pass


class SheetsProvider(ABC):
    @abstractmethod
    async def export_leads(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        leads_data: List[Dict[str, Any]],
        **kwargs
    ) -> Dict[str, Any]:
        pass
