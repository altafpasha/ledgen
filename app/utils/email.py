import re
from typing import List, Optional, Set
from email_validator import validate_email, EmailNotValidError

EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
    re.IGNORECASE,
)

# Common non-lead email extensions / placeholders to exclude
JUNK_EMAIL_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js"}
JUNK_EMAIL_PREFIXES = {"noreply", "no-reply", "mailer-daemon", "postmaster"}


def normalize_email(raw_email: Optional[str]) -> Optional[str]:
    """
    Validates and normalizes an email address. Returns None if invalid or unavailable.
    """
    if not raw_email or not isinstance(raw_email, str):
        return None

    cleaned = raw_email.strip().lower()
    if not cleaned:
        return None

    try:
        validated = validate_email(cleaned, check_deliverability=False)
        return validated.normalized
    except EmailNotValidError:
        # Fallback simple check
        if EMAIL_REGEX.fullmatch(cleaned):
            return cleaned
        return None


def extract_emails_from_text(text: str) -> List[str]:
    """
    Extracts all distinct valid emails found in an arbitrary block of text or HTML.
    """
    if not text:
        return []

    found = EMAIL_REGEX.findall(text)
    valid_emails: Set[str] = set()

    for item in found:
        cleaned = item.strip().lower()
        if any(cleaned.endswith(ext) for ext in JUNK_EMAIL_EXTENSIONS):
            continue
        prefix = cleaned.split("@")[0]
        if prefix in JUNK_EMAIL_PREFIXES:
            continue

        normalized = normalize_email(cleaned)
        if normalized:
            valid_emails.add(normalized)

    return sorted(list(valid_emails))
