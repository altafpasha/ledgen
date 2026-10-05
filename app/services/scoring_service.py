from typing import Any, Dict, Optional, Tuple
from app.db.models.business import Business
from app.db.models.website_analysis import WebsiteAnalysis

TARGET_HIGH_VALUE_CATEGORIES = {
    "restaurant",
    "restaurants",
    "hotel",
    "hotels",
    "clinic",
    "clinics",
    "hospital",
    "retail",
    "textiles",
    "jewellery",
    "supermarket",
    "software",
    "logistics",
    "education",
}

TARGET_PRIORITY_LOCATIONS = {
    "kgf",
    "bangarapet",
    "kolar",
    "bangalore",
    "bengaluru",
    "karnataka",
}


class ScoringService:
    """
    Deterministic & Hybrid Lead Scoring Engine.
    Formula rules:
    - No website: +40
    - Valid business phone: +10
    - Public business email: +10
    - Outdated / insecure website: +15
    - Poor mobile experience: +10
    - Poor performance (> 1500ms): +10
    - Target high-value category: +10
    - Target priority location: +5
    Score capped strictly at 100.
    """

    @classmethod
    def calculate_deterministic_score(
        cls,
        business: Business,
        website_analysis: Optional[WebsiteAnalysis] = None,
    ) -> Tuple[int, Dict[str, int]]:
        breakdown: Dict[str, int] = {}
        total = 0

        # 1. Website absence is our greatest sales opportunity for website development
        if not business.has_website or not business.website:
            breakdown["no_website"] = 40
            total += 40
        else:
            # Website exists - evaluate quality opportunities
            if website_analysis:
                if not website_analysis.is_https or (website_analysis.http_status and website_analysis.http_status >= 400):
                    breakdown["insecure_or_broken_website"] = 15
                    total += 15

                perf = website_analysis.performance_indicators or {}
                if perf.get("is_slow"):
                    breakdown["poor_performance"] = 10
                    total += 10

                if perf.get("missing_viewport"):
                    breakdown["poor_mobile_experience"] = 10
                    total += 10

        # 2. Reached & Contactability
        if business.phone:
            breakdown["valid_phone"] = 10
            total += 10

        if business.email:
            breakdown["public_email"] = 10
            total += 10

        # 3. Category match
        cat = (business.category or "").lower()
        if any(c in cat for c in TARGET_HIGH_VALUE_CATEGORIES):
            breakdown["target_category"] = 10
            total += 10

        # 4. Location match
        city = (business.city or "").lower()
        state = (business.state or "").lower()
        district = (business.district or "").lower()
        if any(loc in city or loc in district or loc in state for loc in TARGET_PRIORITY_LOCATIONS):
            breakdown["priority_location"] = 5
            total += 5

        final_det_score = min(100, max(0, total))
        return final_det_score, breakdown

    @classmethod
    def compute_final_score(cls, deterministic_score: int, ai_score: Optional[int] = None) -> int:
        if ai_score is None:
            return min(100, deterministic_score)

        # 55% deterministic + 45% AI qualification
        combined = int(round(0.55 * deterministic_score + 0.45 * ai_score))
        return min(100, max(0, combined))
