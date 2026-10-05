import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from app.core.exceptions import SSRFSecurityException
from app.core.logging import logger
from app.db.models.business import Business, BusinessContact
from app.db.models.website_analysis import WebsiteAnalysis
from app.providers.apollo import ApolloProvider
from app.providers.base import EnrichmentResult
from app.utils.email import extract_emails_from_text, normalize_email
from app.utils.phone import normalize_phone
from app.utils.ssrf import safe_fetch_url


# Signatures for lightweight technology detection
TECH_SIGNATURES = {
    "WordPress": [r"wp-content", r"wp-includes", r"wp-json"],
    "WooCommerce": [r"woocommerce", r"wc-api", r"cart-fragments"],
    "Shopify": [r"cdn\.shopify\.com", r"shopify\.theme"],
    "Wix": [r"wix\.com", r"wix-warmup-data", r"_wix_"],
    "Squarespace": [r"squarespace\.com", r"static1\.squarespace\.com"],
    "Webflow": [r"webflow\.com", r"assets\.website-files\.com"],
    "Next.js": [r"/_next/", r"__NEXT_DATA__"],
    "React": [r"react", r"react-dom"],
    "Vue": [r"vue\.js", r"v-bind", r"v-on"],
    "Angular": [r"ng-version", r"ng-app"],
    "Laravel": [r"laravel", r"csrf-token"],
    "PHP": [r"\.php", r"X-Powered-By:\s*PHP"],
    "Cloudflare": [r"cf-ray", r"cloudflare"],
    "Nginx": [r"nginx"],
    "Apache": [r"apache"],
}


class EnrichmentService:
    """
    Handles website inspection (SSRF protected) and Apollo contact enrichment.
    """

    @classmethod
    def detect_technologies(cls, html_content: str, headers: Dict[str, str]) -> Dict[str, bool]:
        detected = {}
        header_text = " ".join(f"{k}: {v}" for k, v in headers.items())
        combined_text = f"{header_text}\n{html_content}"

        for tech, patterns in TECH_SIGNATURES.items():
            for p in patterns:
                if re.search(p, combined_text, re.IGNORECASE):
                    detected[tech] = True
                    break

        return detected

    @classmethod
    def check_security_headers(cls, headers: Dict[str, str]) -> Dict[str, bool]:
        lower_headers = {k.lower(): v for k, v in headers.items()}
        return {
            "strict_transport_security": "strict-transport-security" in lower_headers,
            "content_security_policy": "content-security-policy" in lower_headers,
            "x_frame_options": "x-frame-options" in lower_headers,
            "x_content_type_options": "x-content-type-options" in lower_headers,
        }

    @classmethod
    async def inspect_website(cls, url: str) -> Tuple[Optional[WebsiteAnalysis], List[str], List[str]]:
        """
        Inspects public pages (root + contact/about if needed) safely.
        Extracts technologies, security posture, public emails, and phone numbers.
        """
        if not url:
            return None, [], []

        try:
            status_code, html, headers, elapsed_ms = await safe_fetch_url(url, timeout_seconds=10.0)
        except SSRFSecurityException as e:
            logger.warning(f"SSRF blocked website inspection for {url}: {str(e)}")
            return None, [], []
        except Exception as e:
            logger.warning(f"Failed to fetch website {url}: {str(e)}")
            return None, [], []

        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else None
        meta_desc = None
        desc_tag = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
        if desc_tag and desc_tag.get("content"):
            meta_desc = desc_tag["content"].strip()

        # Check viewport for mobile responsiveness
        viewport_tag = soup.find("meta", attrs={"name": "viewport"})
        has_viewport = viewport_tag is not None

        # Extract mailto links and regex emails
        emails_found = set(extract_emails_from_text(html))
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            if href.lower().startswith("mailto:"):
                raw_mail = href[7:].split("?")[0]
                norm = normalize_email(raw_mail)
                if norm:
                    emails_found.add(norm)

        # Extract phones
        phones_found = set()
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            if href.lower().startswith("tel:"):
                raw_phone = href[4:].split("?")[0]
                norm = normalize_phone(raw_phone)
                if norm:
                    phones_found.add(norm)

        # If no contact info on home page, try checking /contact or /about
        if not emails_found:
            for sub_path in ["/contact", "/contact-us", "/about"]:
                sub_url = urljoin(url, sub_path)
                try:
                    _, sub_html, _, _ = await safe_fetch_url(sub_url, timeout_seconds=5.0)
                    sub_emails = extract_emails_from_text(sub_html)
                    for em in sub_emails:
                        emails_found.add(em)
                    if emails_found:
                        break
                except Exception:
                    continue

        is_https = url.strip().lower().startswith("https://")
        technologies = cls.detect_technologies(html, headers)
        security_headers = cls.check_security_headers(headers)
        performance_indicators = {
            "response_time_ms": int(elapsed_ms),
            "is_slow": elapsed_ms > 2000.0,
            "missing_viewport": not has_viewport,
            "content_size_bytes": len(html),
        }

        analysis = WebsiteAnalysis(
            website_url=url,
            is_https=is_https,
            http_status=status_code,
            response_time_ms=int(elapsed_ms),
            title=title[:255] if title else None,
            meta_description=meta_desc[:500] if meta_desc else None,
            technologies=technologies,
            security_headers=security_headers,
            performance_indicators=performance_indicators,
            emails_found=sorted(list(emails_found)),
            phones_found=sorted(list(phones_found)),
            analysis_summary=f"HTTP {status_code}, HTTPS={is_https}, Tech={list(technologies.keys())}",
        )

        return analysis, sorted(list(emails_found)), sorted(list(phones_found))

    @classmethod
    async def enrich_contacts_via_apollo(
        cls,
        business: Business,
        apollo_provider: Optional[ApolloProvider] = None,
    ) -> EnrichmentResult:
        provider = apollo_provider or ApolloProvider()
        return await provider.enrich_business(
            business_name=business.business_name,
            domain=business.website_domain,
            location=business.city,
        )
