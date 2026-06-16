"""
validate_location.py  -  Layer 3 (Execution)

Checks that the delivery location is complete enough for a UAE courier to deliver.
Requires: emirate (known), area, full address, and ideally a Google Maps link.
"""

KNOWN_EMIRATES = {
    "Dubai", "Sharjah", "Ajman", "Umm Al Quwain",
    "Ras Al Khaimah", "Fujairah", "Abu Dhabi",
}
MIN_ADDRESS_LENGTH = 10


def validate_location(emirate, area, address, maps_link=None) -> dict:
    """
    Returns:
        valid:          bool
        issues:         list[str]
        risk_level:     "Low" | "Medium" | "High"
        maps_requested: bool  - True when we should ask for the live location
    """
    issues = []
    em = str(emirate).strip() if emirate else ""
    ar = str(area).strip() if area else ""
    ad = str(address).strip() if address else ""
    ml = str(maps_link).strip() if maps_link else ""

    if not em:
        issues.append("Emirate is missing.")
    elif em not in KNOWN_EMIRATES:
        issues.append(
            f"Emirate '{em}' is not recognised. "
            f"Must be one of: {', '.join(sorted(KNOWN_EMIRATES))}."
        )

    if not ar:
        issues.append("Area is missing.")

    if not ad:
        issues.append("Full address is missing.")
    elif len(ad) < MIN_ADDRESS_LENGTH:
        issues.append(
            "Address is too short — please add building/villa number, street, and a landmark."
        )

    maps_requested = not bool(ml)
    if maps_requested:
        issues.append(
            "Google Maps link / live location not provided — request from customer."
        )

    blocking = any(
        any(kw in i.lower() for kw in ("missing", "not recognised"))
        for i in issues
    )
    risk = "High" if blocking else ("Medium" if issues else "Low")

    return {
        "valid":          len(issues) == 0,
        "issues":         issues,
        "risk_level":     risk,
        "maps_requested": maps_requested,
    }
