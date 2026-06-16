"""
normalize_mobile.py  -  Layer 3 (Execution)

Strips formatting from a raw phone string and converts valid UAE mobile numbers
to E.164 international format (971XXXXXXXXX) used by WhatsApp Cloud API.

Accepted UAE mobile prefixes: 050, 051, 052, 055, 056, 057, 058
"""

import re

UAE_MOBILE_PREFIXES = {"050", "051", "052", "055", "056", "057", "058"}


def normalize_mobile(raw_phone) -> dict:
    """
    Returns:
        original:      str  - input as received
        cleaned:       str  - digits only
        local:         str  - 10-digit local format (05XXXXXXXX) if valid
        international: str  - 971XXXXXXXXX if valid, else ""
        valid:         bool
        reason:        str  - failure reason, or ""
    """
    original = str(raw_phone).strip() if raw_phone is not None else ""
    digits = re.sub(r"\D", "", original)

    # handle international prefix already present
    if digits.startswith("971") and len(digits) == 12:
        digits = "0" + digits[3:]
    elif digits.startswith("00971") and len(digits) == 14:
        digits = "0" + digits[5:]

    if not digits:
        return _fail(original, "", "Phone is empty.")
    if len(digits) != 10:
        return _fail(original, digits,
                     f"UAE mobile must be 10 digits (05XXXXXXXX). Got {len(digits)} digits.")
    if not digits.startswith("0"):
        return _fail(original, digits,
                     "UAE mobile must start with 0 (e.g. 0501234567).")

    prefix = digits[:3]
    if prefix not in UAE_MOBILE_PREFIXES:
        return _fail(original, digits,
                     f"Prefix '{prefix}' is not a recognised UAE mobile prefix "
                     f"(accepted: {', '.join(sorted(UAE_MOBILE_PREFIXES))}).")

    return {
        "original":      original,
        "cleaned":       digits,
        "local":         digits,
        "international": "971" + digits[1:],
        "valid":         True,
        "reason":        "",
    }


def _fail(original, cleaned, reason) -> dict:
    return {
        "original":      original,
        "cleaned":       cleaned,
        "local":         "",
        "international": "",
        "valid":         False,
        "reason":        reason,
    }


if __name__ == "__main__":
    cases = [
        "0501234567", "+971 50 123 4567", "050 123 4567",
        "00971501234567", "050123", "0601234567", "04 123 4567",
    ]
    for c in cases:
        r = normalize_mobile(c)
        tag = "OK  " if r["valid"] else "FAIL"
        print(f"{tag}  {c!r:26} -> local={r['local']} intl={r['international']} {r['reason']}")
