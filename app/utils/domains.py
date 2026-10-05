import re
from typing import Optional
from urllib.parse import urlparse


def extract_domain(url: Optional[str]) -> Optional[str]:
    """
    Extracts the root hostname/domain from a URL, stripping protocol, www, port, and path.
    Example: https://www.my-shop.co.in/about -> my-shop.co.in
    """
    if not url or not isinstance(url, str):
        return None

    cleaned = url.strip().lower()
    if not cleaned:
        return None

    if not cleaned.startswith(("http://", "https://")):
        cleaned = "https://" + cleaned

    try:
        parsed = urlparse(cleaned)
        netloc = parsed.netloc
        if not netloc:
            netloc = parsed.path.split("/")[0]

        # Strip port if present
        domain = netloc.split(":")[0]

        # Strip leading www.
        if domain.startswith("www."):
            domain = domain[4:]

        # Validate that domain has at least one dot and no illegal characters
        if "." in domain and not domain.startswith(".") and not domain.endswith("."):
            return domain
    except Exception:
        pass

    return None


def normalize_website_url(url: Optional[str]) -> Optional[str]:
    """
    Ensures URL has a scheme (https:// preferred) and is properly formatted.
    Returns None if empty or invalid.
    """
    if not url or not isinstance(url, str):
        return None

    cleaned = url.strip()
    if not cleaned:
        return None

    if not cleaned.startswith(("http://", "https://")):
        cleaned = "https://" + cleaned

    try:
        parsed = urlparse(cleaned)
        if parsed.netloc and "." in parsed.netloc:
            return parsed.geturl()
    except Exception:
        pass

    return None
