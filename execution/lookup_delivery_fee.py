"""
lookup_delivery_fee.py  -  Layer 3 (Execution)

Returns the correct delivery fee for an emirate and area from data/delivery_fees.json.
Area override wins over the emirate default. If the emirate is not configured, it
returns found=False so the agent escalates to the owner instead of guessing.
"""

from config import load_delivery_fees


def lookup_delivery_fee(emirate: str, area: str = "") -> dict:
    """Return {found: bool, fee: int|None, source: str, confirmed: bool, reason: str}."""
    data = load_delivery_fees()["emirates"]

    # case-insensitive emirate match
    emirate_key = next((k for k in data if k.lower() == str(emirate).strip().lower()), None)
    if emirate_key is None:
        return {"found": False, "fee": None, "source": "none", "confirmed": False,
                "reason": f"Emirate '{emirate}' is not configured in delivery_fees.json. "
                          f"Owner must add it."}

    rec = data[emirate_key]

    # case-insensitive area override match
    area_key = next((k for k in rec.get("areas", {})
                     if k.lower() == str(area).strip().lower()), None)
    if area_key:
        a = rec["areas"][area_key]
        return {"found": True, "fee": a["fee"], "source": f"{emirate_key}/{area_key}",
                "confirmed": a.get("status") == "confirmed",
                "reason": f"Area-specific fee for {area_key}, {emirate_key}."}

    return {"found": True, "fee": rec["default_fee"], "source": f"{emirate_key} (default)",
            "confirmed": rec.get("status") == "confirmed",
            "reason": f"Emirate default fee for {emirate_key} (no area override)."}


if __name__ == "__main__":
    for e, a in [("Dubai", "JVC"), ("Sharjah", "Al Taawun"), ("Ajman", ""), ("Mars", "")]:
        print(e, a, "->", lookup_delivery_fee(e, a))
