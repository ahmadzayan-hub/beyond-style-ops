"""
verify_order.py  -  Layer 3 (Execution)

The deterministic core of the Beyond Style verification workflow. Given an order
dict, it runs every rule and returns the eight-section result the business uses:

  data_check, missing_or_risky, customer_message, operational_status,
  risk_level, next_action, tracker_update, escalation

This is the reliable replacement for asking an LLM to "check the order". The agent
(Layer 2) decides WHEN to call this and what to do with escalations; the rules
themselves live here so they behave the same every time.

Run a demo:  python verify_order.py
"""

from config import (MANDATORY_FIELDS, PROOF_REQUIRED_METHODS, PAYMENT_METHODS,
                    STATUS_VERIFIED, STATUS_AWAITING, STATUS_CORRECTION, STATUS_BLOCK)
from validate_phone import validate_uae_mobile
from lookup_delivery_fee import lookup_delivery_fee
from calculate_total import lookup_product, compute_total
from draft_whatsapp import draft_message


def _present(value):
    return value is not None and str(value).strip() != ""


def verify_order(order: dict) -> dict:
    """Run all rules. `order` keys should match MANDATORY_FIELDS where known.
    Optional key: customer_confirmed (bool) - has the customer confirmed details."""
    issues = []          # human-readable problems
    data_check = {}      # field -> "present/valid" | "missing" | "invalid"
    blocking = False     # a hard stop (do not pack)
    correction = False   # a fixable mismatch / pending item

    # ---- 1. mandatory field presence ----
    for field in MANDATORY_FIELDS:
        if _present(order.get(field)):
            data_check[field] = "present"
        else:
            data_check[field] = "missing"
            issues.append(f"Missing field: {field.replace('_', ' ')}.")
            blocking = True

    # ---- 2. phone ----
    phone_result = validate_uae_mobile(order.get("phone"))
    if _present(order.get("phone")):
        data_check["phone"] = "valid" if phone_result["valid"] else "invalid"
        if not phone_result["valid"]:
            issues.append(f"Phone: {phone_result['reason']}")
            blocking = True

    # ---- 3. product / colour ----
    product = lookup_product(order.get("product", ""))
    if _present(order.get("product")):
        if not product["found"]:
            issues.append(product["reason"])
            correction = True
        else:
            colour = str(order.get("colour", "")).strip().lower()
            offered = [c.lower() for c in product["colours"]]
            if colour and offered and colour not in offered:
                issues.append(f"Colour '{order.get('colour')}' is not offered for {product['name']} "
                              f"(offered: {', '.join(product['colours'])}).")
                correction = True

    # ---- 4. delivery fee ----
    fee_result = lookup_delivery_fee(order.get("emirate", ""), order.get("area", ""))
    expected_fee = fee_result["fee"]
    if not fee_result["found"]:
        issues.append(fee_result["reason"])
        blocking = True
    else:
        if _present(order.get("delivery_fee")):
            try:
                given_fee = float(order["delivery_fee"])
                if given_fee != float(expected_fee):
                    issues.append(f"Delivery fee should be AED {expected_fee} for "
                                  f"{fee_result['source']}, not AED {int(given_fee)}.")
                    correction = True
            except (TypeError, ValueError):
                issues.append("Delivery fee is not a number; recalculated from policy.")
                correction = True
        if not fee_result["confirmed"]:
            issues.append(f"Delivery fee for {fee_result['source']} is a placeholder. "
                          f"Owner should confirm the real fee.")

    # ---- 5. total ----
    unit_price = order.get("unit_price")
    if product["found"] and _present(unit_price):
        try:
            if float(unit_price) != float(product["unit_price"]):
                issues.append(f"Unit price should be AED {product['unit_price']} for "
                              f"{product['name']}, not AED {unit_price}.")
                correction = True
                unit_price = product["unit_price"]
        except (TypeError, ValueError):
            unit_price = product["unit_price"]
    elif product["found"]:
        unit_price = product["unit_price"]

    computed = compute_total(unit_price, order.get("quantity"),
                             expected_fee if expected_fee is not None else order.get("delivery_fee"))
    expected_total = computed["total"] if computed["ok"] else None
    if computed["ok"] and _present(order.get("total")):
        try:
            given_total = float(order["total"])
            if given_total != float(expected_total):
                issues.append(f"Total should be AED {expected_total} "
                              f"(item AED {computed['line_total']} + delivery AED {expected_fee}), "
                              f"not AED {int(given_total)}.")
                correction = True
        except (TypeError, ValueError):
            correction = True

    # ---- 6. payment ----
    method = order.get("payment_method")
    status = str(order.get("payment_status", "")).strip().lower()
    if _present(method) and method not in PAYMENT_METHODS:
        issues.append(f"Payment method '{method}' is not recognised "
                      f"({', '.join(PAYMENT_METHODS)}).")
        correction = True
    if method in PROOF_REQUIRED_METHODS and status != "confirmed":
        issues.append(f"{method} requires payment proof before dispatch. Status is "
                      f"'{order.get('payment_status')}'.")
        correction = True

    # ---- 7. customer confirmation ----
    customer_confirmed = bool(order.get("customer_confirmed", False))
    if not customer_confirmed and not blocking:
        issues.append("Customer has not yet confirmed the order details.")

    # ---- decide status ----
    if blocking:
        operational_status = STATUS_BLOCK
        risk_level = "High"
        escalation = True
    elif correction:
        operational_status = STATUS_CORRECTION
        risk_level = "High"
        escalation = True
    elif not customer_confirmed:
        operational_status = STATUS_AWAITING
        risk_level = "Medium"
        escalation = False
    else:
        operational_status = STATUS_VERIFIED
        risk_level = "Low"
        escalation = False

    # ---- draft the right customer message ----
    msg_fields = {
        "customer_name": order.get("customer_name", "there"),
        "product": product["name"] if product["found"] else order.get("product", ""),
        "colour": order.get("colour", ""),
        "quantity": order.get("quantity", ""),
        "unit_price": unit_price if unit_price is not None else order.get("unit_price", ""),
        "area": order.get("area", ""),
        "emirate": order.get("emirate", ""),
        "delivery_fee": expected_fee if expected_fee is not None else order.get("delivery_fee", ""),
        "total": expected_total if expected_total is not None else order.get("total", ""),
        "old_total": order.get("total", ""),
    }
    if operational_status == STATUS_BLOCK and not phone_result["valid"]:
        message = draft_message("request_correct_phone", msg_fields)["message"]
        next_action = "Do not pack. Contact the customer for a correct UAE mobile number."
    elif method in PROOF_REQUIRED_METHODS and status != "confirmed" and not blocking:
        message = draft_message("request_payment_proof", msg_fields)["message"]
        next_action = "Do not pack. Request payment proof, then confirm details with the customer."
    elif operational_status == STATUS_VERIFIED:
        message = draft_message("dispatch_notice", msg_fields)["message"]
        next_action = "Order verified. Prepare for packing and dispatch."
    else:
        message = draft_message("confirm_order", msg_fields)["message"]
        next_action = "Send the confirmation message and wait for the customer to confirm or correct."

    return {
        "data_check": data_check,
        "missing_or_risky": issues,
        "customer_message": message,
        "operational_status": operational_status,
        "risk_level": risk_level,
        "next_action": next_action,
        "tracker_update": f"Set status to '{operational_status}', risk '{risk_level}', "
                          f"escalation {'YES' if escalation else 'no'}.",
        "escalation": escalation,
    }


def format_report(result: dict) -> str:
    """Render the eight sections as readable text for a person."""
    lines = []
    lines.append("[DATA CHECK]")
    for f, s in result["data_check"].items():
        lines.append(f"  - {f.replace('_', ' ')}: {s}")
    lines.append("\n[MISSING OR RISKY INFO]")
    if result["missing_or_risky"]:
        for i in result["missing_or_risky"]:
            lines.append(f"  - {i}")
    else:
        lines.append("  - None.")
    lines.append("\n[CUSTOMER MESSAGE DRAFT]")
    lines.append(result["customer_message"])
    lines.append(f"\n[OPERATIONAL STATUS] {result['operational_status']}")
    lines.append(f"[RISK LEVEL] {result['risk_level']}")
    lines.append(f"[NEXT ACTION] {result['next_action']}")
    lines.append(f"[TRACKER UPDATE] {result['tracker_update']}")
    lines.append(f"[ESCALATION REQUIRED?] {'YES' if result['escalation'] else 'No'}")
    return "\n".join(lines)


if __name__ == "__main__":
    demo = {
        "customer_name": "Fatima Al Marri", "phone": "0501234567",
        "emirate": "Dubai", "area": "JVC",
        "address": "Villa 45, Al Manara Street, near Emirates Mall",
        "product": "Gold Layered Chain Necklace", "colour": "Gold", "quantity": 1,
        "unit_price": 89, "delivery_fee": 15, "total": 104,
        "payment_method": "Bank Transfer", "payment_status": "Pending",
    }
    print(format_report(verify_order(demo)))
