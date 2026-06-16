"""
validate_payment.py  -  Layer 3 (Execution)

Applies Beyond Style UAE payment rules:
  - Cash on Delivery : can pack after customer confirmation. No proof required upfront.
  - Bank Transfer    : requires payment screenshot before packing.
  - Debit Card / Card: requires confirmed payment status before packing.
"""

ACCEPTED_METHODS = {"Cash on Delivery", "Bank Transfer", "Debit Card", "Card"}
PROOF_REQUIRED   = {"Bank Transfer", "Debit Card", "Card"}
COD              = "Cash on Delivery"


def validate_payment(payment_method, payment_status) -> dict:
    """
    Returns:
        valid:          bool
        proof_required: bool
        can_pack:       bool  - False when a payment issue blocks packing
        issues:         list[str]
    """
    issues = []
    method = str(payment_method).strip() if payment_method else ""
    status = str(payment_status).strip().lower() if payment_status else ""

    if not method:
        issues.append("Payment method is missing.")
        return {"valid": False, "proof_required": False, "can_pack": False, "issues": issues}

    if method not in ACCEPTED_METHODS:
        issues.append(
            f"Payment method '{method}' is not accepted. "
            f"Use: {', '.join(sorted(ACCEPTED_METHODS - {'Card'}))}."
        )
        return {"valid": False, "proof_required": False, "can_pack": False, "issues": issues}

    proof_required = method in PROOF_REQUIRED

    if not status:
        issues.append("Payment status is missing.")
        return {"valid": False, "proof_required": proof_required, "can_pack": False,
                "issues": issues}

    if proof_required and status != "confirmed":
        issues.append(
            f"{method} requires a payment screenshot before packing. "
            f"Current status: '{payment_status}'."
        )

    return {
        "valid":          len(issues) == 0,
        "proof_required": proof_required,
        "can_pack":       len(issues) == 0,
        "issues":         issues,
    }
