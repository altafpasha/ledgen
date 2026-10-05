from typing import Optional
import phonenumbers


def normalize_phone(raw_phone: Optional[str], default_region: str = "IN") -> Optional[str]:
    """
    Normalizes a phone number to standard E.164 format (e.g. +919876543210).
    If invalid or unavailable, returns None.
    """
    if not raw_phone or not isinstance(raw_phone, str):
        return None

    cleaned = raw_phone.strip()
    if not cleaned:
        return None

    try:
        # If number doesn't start with +, try parsing with default_region (India 'IN')
        parsed = phonenumbers.parse(cleaned, default_region)
        if phonenumbers.is_possible_number(parsed) and phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except Exception:
        pass

    # Fallback cleanup for local numbers if library is too strict
    digits = "".join(ch for ch in cleaned if ch.isdigit())
    if len(digits) == 10 and default_region == "IN":
        return f"+91{digits}"
    elif len(digits) == 11 and digits.startswith("0") and default_region == "IN":
        return f"+91{digits[1:]}"
    elif len(digits) == 12 and digits.startswith("91"):
        return f"+{digits}"

    return None
