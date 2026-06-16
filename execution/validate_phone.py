"""
validate_phone.py  -  Layer 3 (Execution)

Deterministic UAE mobile validation. Returns whether a number is valid plus a
normalised national form (0XXXXXXXXX) and a clear reason when it is not.

Examples (these match real Beyond Style test cases):
    validate_uae_mobile("0501234567") -> valid
    validate_uae_mobile("050123")     -> invalid (too short)
"""

import re
from config import VALID_UAE_PREFIXES, UAE_MOBILE_LENGTH


def normalise(raw: str) -> str:
    """Strip spaces, dashes, brackets; convert +971/971 international form to
    national 0XXXXXXXXX form. Does not judge validity, only cleans format."""
    if raw is None:
        return ""
    digits = re.sub(r"[^\d+]", "", str(raw))
    # International forms: +9715XXXXXXXX or 9715XXXXXXXX  ->  05XXXXXXXX
    if digits.startswith("+971"):
        digits = "0" + digits[4:]
    elif digits.startswith("971"):
        digits = "0" + digits[3:]
    return digits


def validate_uae_mobile(raw: str) -> dict:
    """Return a dict: {valid: bool, normalised: str, reason: str}."""
    normalised = normalise(raw)

    if normalised == "":
        return {"valid": False, "normalised": "", "reason": "No phone number provided."}

    if not normalised.isdigit():
        return {"valid": False, "normalised": normalised,
                "reason": "Phone contains characters that are not digits."}

    if len(normalised) != UAE_MOBILE_LENGTH:
        return {"valid": False, "normalised": normalised,
                "reason": f"Phone must be {UAE_MOBILE_LENGTH} digits in the form 05XXXXXXXX. "
                          f"Got {len(normalised)} digits."}

    prefix = normalised[:3]
    if prefix not in VALID_UAE_PREFIXES:
        return {"valid": False, "normalised": normalised,
                "reason": f"Prefix {prefix} is not a recognised UAE mobile prefix "
                          f"({', '.join(VALID_UAE_PREFIXES)})."}

    return {"valid": True, "normalised": normalised, "reason": "Valid UAE mobile."}


if __name__ == "__main__":
    # quick manual check
    for n in ["0501234567", "050123", "+971501234567", "05a1234567", ""]:
        print(n or "(empty)", "->", validate_uae_mobile(n))
