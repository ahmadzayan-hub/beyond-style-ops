"""
calculate_delivery_fee.py  -  Layer 3 (Execution)

Looks up the delivery fee for a given emirate/area from data/delivery_fees.json.
Supports area-specific overrides; falls back to emirate default.
Adds an express surcharge of AED 25 when express=True.
"""

import json
import os

_DATA_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data", "delivery_fees.json"
)


def _load():
    with open(_DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def calculate_delivery_fee(emirate: str, area: str = "", express: bool = False) -> dict:
    """
    Returns:
        fee:              int | None
        confirmed:        bool
        source:           str  - e.g. "Dubai/JVC (area)" or "Dubai (default)"
        found:            bool
        reason:           str
        express_surcharge:int
        total_fee:        int | None
    """
    try:
        data = _load()
    except Exception as e:
        return _not_found(f"Could not load delivery fee data: {e}")

    em_clean = str(emirate).strip()
    ar_clean = str(area).strip()

    matched = next(
        (k for k in data.get("emirates", {}) if k.lower() == em_clean.lower()),
        None,
    )
    if not matched:
        return _not_found(
            f"Emirate '{em_clean}' is not in the delivery fee table. "
            "Add it to data/delivery_fees.json before proceeding."
        )

    em_data = data["emirates"][matched]
    surcharge = 25 if express else 0

    # area override
    for area_key, area_val in em_data.get("areas", {}).items():
        if area_key.lower() == ar_clean.lower():
            fee = area_val["fee"]
            confirmed = area_val.get("status") == "confirmed"
            source = f"{matched}/{area_key} (area override)"
            return _found(fee, confirmed, source, surcharge)

    # emirate default
    fee = em_data.get("default_fee")
    confirmed = em_data.get("status") == "confirmed"
    source = f"{matched} (default)"
    return _found(fee, confirmed, source, surcharge)


def _found(fee, confirmed, source, surcharge) -> dict:
    reason = "" if confirmed else f"Fee for {source} is a placeholder — confirm with owner."
    return {
        "fee":               fee,
        "confirmed":         confirmed,
        "source":            source,
        "found":             True,
        "reason":            reason,
        "express_surcharge": surcharge,
        "total_fee":         fee + surcharge if fee is not None else None,
    }


def _not_found(reason) -> dict:
    return {
        "fee":               None,
        "confirmed":         False,
        "source":            "",
        "found":             False,
        "reason":            reason,
        "express_surcharge": 0,
        "total_fee":         None,
    }
