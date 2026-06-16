"""
risk_score_order.py  -  Layer 3 (Execution)

Computes risk level from the list of issues found during order validation.
"""

_HIGH_KEYWORDS   = ["missing", "invalid", "not recognised", "not in the delivery fee",
                     "cannot be negative", "must be greater than zero", "empty"]
_MEDIUM_KEYWORDS = ["placeholder", "pending", "proof", "confirmation", "maps",
                     "too short", "should be"]


def risk_score_order(issues: list, blocking: bool = False) -> dict:
    """
    Returns:
        risk_level:   "Low" | "Medium" | "High"
        risk_score:   int
        risk_factors: list[str]
    """
    if blocking or any(
        any(kw in i.lower() for kw in _HIGH_KEYWORDS) for i in issues
    ):
        level = "High"
    elif issues and any(
        any(kw in i.lower() for kw in _MEDIUM_KEYWORDS) for i in issues
    ):
        level = "Medium"
    elif issues:
        level = "Medium"
    else:
        level = "Low"

    return {"risk_level": level, "risk_score": len(issues), "risk_factors": issues}
