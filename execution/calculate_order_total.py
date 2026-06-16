"""
calculate_order_total.py  -  Layer 3 (Execution)

Computes the expected line total and grand total for an order.
"""


def calculate_order_total(unit_price, quantity, delivery_fee) -> dict:
    """
    Returns:
        ok:         bool
        line_total: float | None  - unit_price × quantity
        total:      float | None  - line_total + delivery_fee
        reason:     str
    """
    try:
        up  = float(unit_price)
        qty = int(quantity)
        df  = float(delivery_fee)
    except (TypeError, ValueError) as e:
        return {"ok": False, "line_total": None, "total": None,
                "reason": f"Cannot calculate total: {e}"}

    if up <= 0:
        return {"ok": False, "line_total": None, "total": None,
                "reason": "Unit price must be greater than zero."}
    if qty <= 0:
        return {"ok": False, "line_total": None, "total": None,
                "reason": "Quantity must be at least 1."}
    if df < 0:
        return {"ok": False, "line_total": None, "total": None,
                "reason": "Delivery fee cannot be negative."}

    line_total = round(up * qty, 2)
    return {
        "ok":         True,
        "line_total": line_total,
        "total":      round(line_total + df, 2),
        "reason":     "",
    }
