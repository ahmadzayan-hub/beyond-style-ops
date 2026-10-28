"""ops/payments.py — Payment update rules shared by the web API.

Mirrors the rules that pages/2_Payments.py applied before the web app existed.
Pure functions only: no sheet access here.
"""

from ops.config import PAYMENT_STATUSES


class PaymentRuleError(ValueError):
    """Raised when a payment update breaks a business rule. Message is safe to show the owner."""


def build_payment_updates(
    status: str,
    payment_reference: str,
    payment_link: str,
    cod_expected: str,
    cod_collected: str,
    notes: str,
) -> tuple[dict, dict]:
    """Return (Payments tab updates, Master Orders updates) for one order.

    Raises PaymentRuleError for an unknown status or a COD Confirmed order
    without an expected COD amount.
    """
    if status not in PAYMENT_STATUSES:
        raise PaymentRuleError(f"Payment status must be one of: {', '.join(PAYMENT_STATUSES)}.")

    cod_expected = cod_expected.strip()
    if status == "Paid Online":
        cod_expected = "0"
    if status == "COD Confirmed" and not cod_expected:
        raise PaymentRuleError("COD Expected must be filled in for a COD Confirmed order.")

    payments_updates = {
        "Payment Status": status,
        "Payment Reference": payment_reference,
        "Payment Link": payment_link,
        "COD Expected": cod_expected,
        "COD Collected": cod_collected,
        "Notes": notes,
    }

    master_updates = {"Payment Status": status}
    if status == "Paid Online":
        master_updates["COD Expected"] = "0"
        master_updates["Order Status"] = "Paid Online"
    elif status == "COD Confirmed":
        master_updates["Order Status"] = "COD Confirmed"
        master_updates["COD Expected"] = cod_expected
    elif status == "Payment Link Sent":
        master_updates["Order Status"] = "Payment Link Sent"

    return payments_updates, master_updates
