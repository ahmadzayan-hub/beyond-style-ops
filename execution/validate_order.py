"""
validate_order.py  -  Layer 3 (Execution) — Module 1

Main orchestrator for Beyond Style UAE order verification.
Calls every specialist script and returns the 8-section result.

Run demo:  python validate_order.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from normalize_mobile       import normalize_mobile
from validate_location      import validate_location
from calculate_delivery_fee import calculate_delivery_fee
from calculate_order_total  import calculate_order_total
from validate_payment       import validate_payment
from risk_score_order       import risk_score_order
from generate_whatsapp_message import generate_whatsapp_message

STATUS_VERIFIED   = "Verified"
STATUS_AWAITING   = "Awaiting Confirmation"
STATUS_CORRECTION = "Needs Correction"
STATUS_BLOCK      = "High Risk / Do Not Pack"

MANDATORY_FIELDS = [
    "customer_name", "phone", "emirate", "area", "address",
    "product", "colour", "quantity", "unit_price",
    "delivery_fee", "total", "payment_method", "payment_status",
]


def _present(v):
    return v is not None and str(v).strip() != ""


def validate_order(order: dict) -> dict:
    issues     = []
    data_check = {}
    blocking   = False
    correction = False

    # 1. mandatory field presence
    for field in MANDATORY_FIELDS:
        if _present(order.get(field)):
            data_check[field] = "present"
        else:
            data_check[field] = "missing"
            issues.append(f"Missing field: {field.replace('_', ' ')}.")
            blocking = True

    # 2. phone
    phone_r = normalize_mobile(order.get("phone"))
    if _present(order.get("phone")):
        data_check["phone"] = "valid" if phone_r["valid"] else "invalid"
        if not phone_r["valid"]:
            issues.append(f"Phone: {phone_r['reason']}")
            blocking = True

    # 3. location
    loc_r = validate_location(
        order.get("emirate", ""), order.get("area", ""),
        order.get("address", ""), order.get("maps_link", ""),
    )
    for issue in loc_r["issues"]:
        if issue not in issues:
            if "missing" in issue.lower() or "not recognised" in issue.lower():
                blocking = True
            elif "not provided" in issue.lower() and "maps" in issue.lower():
                pass  # maps link is optional — note it but don't change status
            else:
                correction = True
            issues.append(issue)

    # 4. delivery fee
    fee_r    = calculate_delivery_fee(order.get("emirate", ""), order.get("area", ""))
    exp_fee  = fee_r["total_fee"]

    if not fee_r["found"]:
        issues.append(fee_r["reason"])
        blocking = True
    else:
        if _present(order.get("delivery_fee")):
            try:
                given = float(order["delivery_fee"])
                if given != float(exp_fee):
                    issues.append(
                        f"Delivery fee should be AED {exp_fee} for "
                        f"{fee_r['source']}, not AED {int(given)}."
                    )
                    correction = True
            except (TypeError, ValueError):
                issues.append("Delivery fee is not a valid number.")
                correction = True
        if not fee_r["confirmed"]:
            issues.append(fee_r["reason"])

    # 5. order total
    total_r   = calculate_order_total(
        order.get("unit_price"), order.get("quantity"),
        exp_fee if exp_fee is not None else order.get("delivery_fee"),
    )
    exp_total = total_r["total"] if total_r["ok"] else None

    if total_r["ok"] and _present(order.get("total")):
        try:
            given_total = float(order["total"])
            if given_total != float(exp_total):
                issues.append(
                    f"Total should be AED {exp_total} "
                    f"(AED {total_r['line_total']} item + AED {exp_fee} delivery), "
                    f"not AED {int(given_total)}."
                )
                correction = True
        except (TypeError, ValueError):
            issues.append("Total amount is not a valid number.")
            correction = True

    # 6. payment
    pay_r = validate_payment(order.get("payment_method"), order.get("payment_status"))
    for issue in pay_r["issues"]:
        issues.append(issue)
        correction = True

    # 7. customer confirmation
    confirmed = bool(order.get("customer_confirmed", False))
    if not confirmed and not blocking:
        issues.append("Customer has not yet confirmed the order details.")

    # decide status
    risk_r = risk_score_order(issues, blocking)

    if blocking:
        status, risk, escalation = STATUS_BLOCK, "High", True
    elif correction:
        status, risk, escalation = STATUS_CORRECTION, risk_r["risk_level"], True
    elif not confirmed:
        status, risk, escalation = STATUS_AWAITING, "Medium", False
    else:
        status, risk, escalation = STATUS_VERIFIED, "Low", False

    # pick message type
    msg_fields = {
        "customer_name":  order.get("customer_name", ""),
        "phone":          phone_r["local"] or order.get("phone", ""),
        "emirate":        order.get("emirate", ""),
        "area":           order.get("area", ""),
        "address":        order.get("address", ""),
        "maps_link":      order.get("maps_link", ""),
        "product":        order.get("product", ""),
        "colour":         order.get("colour", ""),
        "quantity":       order.get("quantity", ""),
        "unit_price":     order.get("unit_price", ""),
        "delivery_fee":   exp_fee if exp_fee is not None else order.get("delivery_fee", ""),
        "total":          exp_total if exp_total is not None else order.get("total", ""),
        "payment_method": order.get("payment_method", ""),
    }

    if not phone_r["valid"] and blocking:
        msg_type   = "phone_invalid"
        next_action = "Do not pack. Contact the customer for a correct UAE mobile number."
    elif loc_r.get("maps_requested") and not blocking:
        msg_type   = "location_request"
        next_action = "Request full address and Google Maps location from the customer."
    elif pay_r["proof_required"] and not pay_r["can_pack"] and not blocking:
        msg_type   = "payment_proof_request"
        next_action = "Do not pack. Request payment screenshot from the customer."
    elif correction:
        try:
            fee_mismatch = (
                _present(order.get("delivery_fee")) and
                float(order["delivery_fee"]) != float(exp_fee or 0)
            )
        except (TypeError, ValueError):
            fee_mismatch = False
        msg_type   = "correction_fee" if fee_mismatch else "confirm_order"
        next_action = "Send the correction message and wait for CONFIRM reply."
    elif status == STATUS_VERIFIED:
        msg_type   = "dispatch_confirmed"
        next_action = "Order verified. Pack and hand to courier."
    else:
        msg_type   = "confirm_order"
        next_action = "Send confirmation message and wait for CONFIRM reply."

    msg_r    = generate_whatsapp_message(msg_type, msg_fields)
    message  = msg_r["combined"] if msg_r["ok"] else "[Message generation failed]"

    return {
        "data_check":         data_check,
        "missing_or_risky":   issues,
        "customer_message":   message,
        "operational_status": status,
        "risk_level":         risk,
        "next_action":        next_action,
        "tracker_update":     (
            f"Set status to '{status}', risk '{risk}', "
            f"escalation {'YES' if escalation else 'no'}."
        ),
        "escalation":         escalation,
        "phone_normalized":   phone_r,
        "location":           loc_r,
        "message_type":       msg_type,
    }


def format_report(result: dict) -> str:
    lines = ["[DATA CHECK]"]
    for f, s in result["data_check"].items():
        lines.append(f"  - {f.replace('_', ' ')}: {s}")
    lines.append("\n[MISSING OR RISKY INFO]")
    for i in result["missing_or_risky"]:
        lines.append(f"  - {i}")
    if not result["missing_or_risky"]:
        lines.append("  - None.")
    lines.append("\n[CUSTOMER MESSAGE DRAFT]")
    lines.append(result["customer_message"])
    lines.append(f"\n[OPERATIONAL STATUS] {result['operational_status']}")
    lines.append(f"[RISK LEVEL]         {result['risk_level']}")
    lines.append(f"[NEXT ACTION]        {result['next_action']}")
    lines.append(f"[TRACKER UPDATE]     {result['tracker_update']}")
    lines.append(f"[ESCALATION?]        {'YES' if result['escalation'] else 'No'}")
    return "\n".join(lines)


if __name__ == "__main__":
    demo = {
        "customer_name":      "Fatima Al Marri",
        "phone":              "0501234567",
        "emirate":            "Dubai",
        "area":               "JVC",
        "address":            "Villa 45, Al Manara Street, near Emirates Mall",
        "maps_link":          "",
        "product":            "Masha'Allah Bracelet",
        "colour":             "Gold",
        "quantity":           1,
        "unit_price":         79,
        "delivery_fee":       25,
        "total":              104,
        "payment_method":     "Bank Transfer",
        "payment_status":     "Pending",
        "customer_confirmed": False,
    }
    print(format_report(validate_order(demo)))
