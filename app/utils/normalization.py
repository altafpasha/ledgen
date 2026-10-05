import re
from typing import Optional

# Entity suffixes to strip during fuzzy/normalized comparisons
LEGAL_SUFFIXES = [
    r"\bpvt\.?\s*ltd\.?",
    r"\bprivate\s*limited\b",
    r"\bltd\.?",
    r"\blimited\b",
    r"\bllc\b",
    r"\binc\.?",
    r"\bincorporated\b",
    r"\bcorp\.?",
    r"\bcorporation\b",
    r"\bco\.?",
    r"\bcompany\b",
    r"\benterprises?\b",
    r"\bservices?\b",
    r"\bsolutions?\b",
]

SUFFIX_REGEX = re.compile(r"|".join(LEGAL_SUFFIXES), re.IGNORECASE)
NON_ALPHANUMERIC = re.compile(r"[^\w\s]")


def normalize_business_name(raw_name: Optional[str]) -> Optional[str]:
    """
    Produces a normalized business name for deduplication:
    1. Lowercase
    2. Remove legal suffixes (pvt ltd, llc, etc.)
    3. Remove punctuation
    4. Collapse spaces
    """
    if not raw_name or not isinstance(raw_name, str):
        return None

    cleaned = raw_name.strip().lower()
    if not cleaned:
        return None

    # Strip legal entity suffixes
    cleaned = SUFFIX_REGEX.sub(" ", cleaned)

    # Remove punctuation
    cleaned = NON_ALPHANUMERIC.sub(" ", cleaned)

    # Collapse multiple spaces
    normalized = " ".join(cleaned.split())
    return normalized if normalized else None


def normalize_address(raw_address: Optional[str]) -> Optional[str]:
    """
    Normalizes an address string for deduplication comparison.
    """
    if not raw_address or not isinstance(raw_address, str):
        return None

    cleaned = raw_address.strip().lower()
    if not cleaned:
        return None

    # Replace newlines and multiple whitespace
    cleaned = " ".join(cleaned.split())
    # Remove excessive punctuation
    cleaned = re.sub(r"[,;:\-#/]+", " ", cleaned)
    return " ".join(cleaned.split())
