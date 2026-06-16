"""
calculate_total.py  -  Layer 3 (Execution)

Two deterministic helpers:
  - lookup_product(): finds a product in the catalogue and its expected price/colours
  - compute_total(): unit_price * quantity + delivery_fee

Used to detect mismatches between what the customer stated and what the rules say.
"""

from config import load_catalogue


def lookup_product(name: str) -> dict:
    """Return {found, name, unit_price, colours, reason} for a catalogue product."""
    products = load_catalogue()["products"]
    key = str(name).strip().lower()
    for p in products:
        if p["name"].strip().lower() == key:
            return {"found": True, "name": p["name"], "unit_price": p["unit_price"],
                    "colours": p.get("colours", []), "reason": "Product found in catalogue."}
    return {"found": False, "name": name, "unit_price": None, "colours": [],
            "reason": f"Product '{name}' is not in the catalogue. Owner must add it or correct the name."}


def compute_total(unit_price, quantity, delivery_fee) -> dict:
    """Return {ok, line_total, total, reason}. ok=False if any input is missing/invalid."""
    try:
        unit_price = float(unit_price)
        quantity = int(quantity)
        delivery_fee = float(delivery_fee)
    except (TypeError, ValueError):
        return {"ok": False, "line_total": None, "total": None,
                "reason": "Cannot compute total: unit price, quantity, or delivery fee is missing or not a number."}

    if quantity <= 0:
        return {"ok": False, "line_total": None, "total": None,
                "reason": "Quantity must be a positive whole number."}

    line_total = unit_price * quantity
    total = line_total + delivery_fee
    # return ints when values are whole, for clean AED display
    fmt = lambda v: int(v) if float(v).is_integer() else round(v, 2)
    return {"ok": True, "line_total": fmt(line_total), "total": fmt(total),
            "reason": "Total computed."}


if __name__ == "__main__":
    print(lookup_product("Gold Layered Chain Necklace"))
    print(compute_total(89, 1, 15))   # -> 104
    print(compute_total(89, 1, 20))   # -> 109
    print(compute_total(65, 2, 20))   # -> 150
