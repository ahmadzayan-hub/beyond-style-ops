"""
daily_escalation_summary.py  -  Layer 3 (Execution)

Builds one plain-language summary for the owner from orders that need attention
before packing: status "High Risk / Do Not Pack" or risk level "High".
Takes already-validated results from validate_order; does not re-score anything.
"""

STATUS_BLOCK = "High Risk / Do Not Pack"


def summarize_high_risk_orders(pairs: list, day: str) -> dict:
    """
    pairs: list of (order, result) tuples, where result is a validate_order output.
    Returns:
        count:  int
        report: str   - plain-language summary, empty string when count is 0
        orders: list[dict] - customer, product, status, reasons for each flagged order
    """
    flagged = []
    for order, result in pairs:
        if result.get("operational_status") == STATUS_BLOCK or result.get("risk_level") == "High":
            flagged.append({
                "customer": order.get("customer_name", "Unknown"),
                "product":  order.get("product", "-"),
                "status":   result.get("operational_status", ""),
                "reasons":  list(result.get("missing_or_risky", [])),
            })

    if not flagged:
        return {"count": 0, "report": "", "orders": []}

    lines = [
        f"High-risk orders for {day}: {len(flagged)}",
        "Do not pack these until each issue is resolved.",
        "",
    ]
    for n, item in enumerate(flagged, 1):
        lines.append(f"{n}. {item['customer']} - {item['product']} ({item['status']})")
        for reason in item["reasons"]:
            lines.append(f"   - {reason}")

    return {"count": len(flagged), "report": "\n".join(lines), "orders": flagged}
