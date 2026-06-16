"""
validate_mobile.py  -  Layer 3 (Execution)

Validates a UAE mobile number and returns a courier-call reminder note.
Thin wrapper around normalize_mobile.
"""

from normalize_mobile import normalize_mobile


def validate_mobile(raw_phone) -> dict:
    """
    Returns:
        valid:         bool
        local:         str  - 10-digit local format
        international: str  - E.164 format for WhatsApp API
        reason:        str  - failure reason, or ""
        courier_note:  str  - reminder if valid
    """
    r = normalize_mobile(raw_phone)
    return {
        "valid":         r["valid"],
        "local":         r["local"],
        "international": r["international"],
        "reason":        r["reason"],
        "courier_note":  (
            "Confirm the number can receive voice calls from the courier."
            if r["valid"] else ""
        ),
    }
