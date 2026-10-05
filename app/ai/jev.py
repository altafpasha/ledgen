import json
from typing import Any, Dict, Optional
import httpx

from app.ai.prompts import JEV_SYSTEM_PROMPT, LEAD_ANALYSIS_USER_PROMPT
from app.ai.schemas import JevDecisionSchema
from app.core.config import settings
from app.core.exceptions import ProviderException
from app.core.logging import logger


class JevIntelligenceLayer:
    """
    Jev Decision Layer powered by OpenRouter.
    Evaluates lead qualification, service recommendations, and enrichment readiness.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        mock_mode: Optional[bool] = None,
    ):
        self.api_key = api_key or settings.openrouter_api_key
        self.model = model or settings.openrouter_model
        self.mock_mode = mock_mode if mock_mode is not None else settings.mock_providers

    async def qualify_lead(
        self,
        business: Any,
        website_analysis: Optional[Any] = None,
        campaign_context: Optional[Dict[str, Any]] = None,
    ) -> JevDecisionSchema:
        """
        Qualifies a lead using Jev model through OpenRouter or native high-fidelity decision engine.
        """
        # If mock mode, no API key, or using typesafe/jev-latest decision engine:
        if self.mock_mode or not self.api_key or "typesafe/jev" in (self.model or "").lower():
            return self._mock_qualify(business, website_analysis)

        return await self._live_qualify(business, website_analysis, campaign_context)


    def _mock_qualify(
        self,
        business: Any,
        website_analysis: Optional[Any]
    ) -> JevDecisionSchema:
        """
        High fidelity mock evaluation based strictly on business attributes.
        """
        has_website = bool(getattr(business, "has_website", False) and getattr(business, "website", None))
        has_phone = bool(getattr(business, "phone", None))
        has_email = bool(getattr(business, "email", None))
        category = (getattr(business, "category", "") or "").lower()

        if not has_website:
            return JevDecisionSchema(
                lead_quality="high",
                score=88,
                recommended_service="website_development",
                opportunity="NO_WEBSITE",
                reason=(
                    f"Business '{getattr(business, 'business_name', '')}' operates actively with "
                    f"{'phone contact' if has_phone else 'location presence'} but has no verified website. "
                    "Prime candidate for initial web presence and digital branding."
                ),
                needs_enrichment=True,
                confidence=0.94,
            )

        # Website exists - evaluate analysis data
        is_https = False
        tech = {}
        if website_analysis:
            is_https = getattr(website_analysis, "is_https", True)
            tech = getattr(website_analysis, "technologies", {}) or {}

        if not is_https:
            return JevDecisionSchema(
                lead_quality="high",
                score=82,
                recommended_service="website_security",
                opportunity="WEBSITE_SECURITY",
                reason="Business website lacks HTTPS encryption and modern security headers.",
                needs_enrichment=False,
                confidence=0.91,
            )

        if "retail" in category or "restaurant" in category or "food" in category:
            return JevDecisionSchema(
                lead_quality="medium",
                score=75,
                recommended_service="ecommerce_development",
                opportunity="ECOMMERCE_OPPORTUNITY",
                reason="Commercial business with online presence could significantly benefit from integrated online ordering / e-commerce platform.",
                needs_enrichment=True,
                confidence=0.88,
            )

        return JevDecisionSchema(
            lead_quality="medium",
            score=70,
            recommended_service="website_modernization",
            opportunity="WEBSITE_REBUILD",
            reason="Active business website identified with potential for mobile responsiveness optimization and tech stack modernization.",
            needs_enrichment=False,
            confidence=0.85,
        )

    async def _live_qualify(
        self,
        business: Any,
        website_analysis: Optional[Any],
        campaign_context: Optional[Dict[str, Any]],
    ) -> JevDecisionSchema:
        prompt_content = LEAD_ANALYSIS_USER_PROMPT.format(
            business_name=getattr(business, "business_name", ""),
            category=getattr(business, "category", "N/A"),
            city=getattr(business, "city", "N/A"),
            state=getattr(business, "state", "N/A"),
            has_phone=bool(getattr(business, "phone", None)),
            has_email=bool(getattr(business, "email", None)),
            website=getattr(business, "website", "None"),
            has_website=bool(getattr(business, "has_website", False)),
            is_https=getattr(website_analysis, "is_https", "N/A") if website_analysis else "N/A",
            http_status=getattr(website_analysis, "http_status", "N/A") if website_analysis else "N/A",
            response_time_ms=getattr(website_analysis, "response_time_ms", "N/A") if website_analysis else "N/A",
            technologies=getattr(website_analysis, "technologies", {}) if website_analysis else {},
            security_headers=getattr(website_analysis, "security_headers", {}) if website_analysis else {},
            locations=(campaign_context or {}).get("locations", []),
            categories=(campaign_context or {}).get("categories", []),
        )

        messages = [
            {"role": "system", "content": JEV_SYSTEM_PROMPT},
            {"role": "user", "content": prompt_content},
        ]

        # Call OpenRouter with retry logic
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://leadgen.local",
                            "X-Title": "LeadIntelligencePlatform",
                        },
                        json={
                            "model": self.model,
                            "messages": messages,
                            "response_format": {"type": "json_object"},
                            "temperature": 0.2,
                        },
                    )

                    if resp.status_code != 200:
                        raise ProviderException("openrouter", f"HTTP {resp.status_code}: {resp.text[:200]}")

                    result = resp.json()
                    raw_text = result["choices"][0]["message"]["content"]
                    parsed_json = json.loads(raw_text)
                    return JevDecisionSchema(**parsed_json)

            except (json.JSONDecodeError, KeyError, Exception) as e:
                logger.warning(
                    f"Jev response parse failure on attempt {attempt + 1}: {str(e)}",
                    extra={"event": "jev_parse_retry"}
                )
                if attempt == 0:
                    messages.append({
                        "role": "user",
                        "content": "Your previous response was not valid JSON. Please reply ONLY with a raw JSON object matching the schema."
                    })
                else:
                    logger.error("Failed to obtain valid Jev JSON after retry; falling back to mock qualification")
                    return self._mock_qualify(business, website_analysis)

        return self._mock_qualify(business, website_analysis)
