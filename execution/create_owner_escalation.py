"""
create_owner_escalation.py  -  Layer 3 (Execution)

Formats a plain-language escalation report for the business owner when an order
requires human review before any packing or dispatch.
"""

from datetime import datetime


def create_owner_escalation(order: dict, result: dict) -> dict:
    """
    Returns:
        required:  bool
        report:    str   - formatted plain-language report
        reasons:   list[str]
        timestamp: str
    """
    required = result.get("escalation", False)
    issues   = result.get("missing_or_risky", [])
    ts       = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    if not required:
        return {"required": False, "report": "", "reasons": [], "timestamp": ts}

    lines = [
        f"⚠️  ESCALATION REQUIRED — {ts}",
        "─" * 50,
        f"Customer : {order.get('customer_name', 'Unknown')}",
        f"Phone    : {order.get('phone', '—')}",
        f"Product  : {order.get('product', '—')}",
        f"Location : {order.get('area', '—')}, {order.get('emirate', '—')}",
        f"Status   : {result.get('operational_status', '')}",
        f"Risk     : {result.get('risk_level', '')}",
        "",
        "Issues that need your attention:",
    ]
    for i, issue in enumerate(issues, 1):
        lines.append(f"  {i}. {issue}")

    lines += [
        "",
        f"Next action: {result.get('next_action', '')}",
        "",
        "DO NOT pack or dispatch until these issues are resolved.",
        "─" * 50,
    ]

    return {
        "required":  True,
        "report":    "\n".join(lines),
        "reasons":   issues,
        "timestamp": ts,
    }
