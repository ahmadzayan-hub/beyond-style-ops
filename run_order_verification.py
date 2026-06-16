"""
run_order_verification.py  -  Layer 2 (Orchestration)

Main entry point for the Beyond Style UAE order verification pipeline.
Pass an order dict and it runs the full pipeline:

  Phase 1 (live now):
    1. Validate the order (phone, location, payment, product, fee)
    2. Generate bilingual WhatsApp message draft
    3. Send verification report email to info@beyondstyle.ae
    4. Write result to Master Orders Google Sheet

  Phase 2 (activate once WhatsApp SIM is ready):
    5. Send WhatsApp message to customer
       Set WHATSAPP_PHASE2_ENABLED=true in .env to activate

Usage:
    from run_order_verification import run_order_verification
    summary = run_order_verification(order)
    print(summary["status"])

Direct test run:
    python run_order_verification.py
"""

import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "execution"))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Phase 2 gate ──────────────────────────────────────────────────────────────
_WHATSAPP_ENABLED = os.getenv("WHATSAPP_PHASE2_ENABLED", "false").lower() == "true"


def run_order_verification(order: dict) -> dict:
    """
    Full order verification pipeline.

    Args:
        order: dict with these fields (all required unless noted):
            customer_name, phone, emirate, area, address,
            product, colour, quantity, unit_price, delivery_fee,
            total, payment_method, payment_status,
            maps_link (optional), order_id (optional)

    Returns:
        status:         str   operational_status from verification
        risk_level:     str
        escalation:     bool
        email_sent:     bool
        email_dry_run:  bool
        whatsapp_sent:  bool  (False until Phase 2 enabled)
        sheet_row:      int   row written in Master Orders
        sheet_action:   str   "appended" | "updated"
        errors:         list  any non-fatal errors encountered
        result:         dict  full 8-section verification result
    """
    errors   = []
    order_id = order.get("order_id")

    # ── Step 1: Validate order ────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  BEYOND STYLE UAE — ORDER VERIFICATION")
    print(f"{'='*60}")
    print(f"  Customer: {order.get('customer_name', '')}")
    print(f"  Phone:    {order.get('phone', '')}")
    print(f"  Product:  {order.get('product', '')} × {order.get('quantity', '')}")
    print(f"{'='*60}\n")

    from validate_order import validate_order
    result = validate_order(order)

    status     = result.get("operational_status", "Unknown")
    risk       = result.get("risk_level", "Unknown")
    escalation = result.get("escalation", False)

    print(f"  Status:     {status}")
    print(f"  Risk:       {risk}")
    print(f"  Escalation: {'YES' if escalation else 'No'}")

    issues = result.get("missing_or_risky", [])
    if issues:
        print(f"\n  Issues:")
        for i in issues:
            print(f"    - {i}")

    print(f"\n  Next action: {result.get('next_action', '')}")

    # ── Step 2: Send email (Phase 1) ──────────────────────────────────────────
    print(f"\n[Phase 1] Sending verification email...")
    from send_email import send_verification_email
    email_result = send_verification_email(order, result)

    if email_result["sent"]:
        mode = "(dry run)" if email_result["dry_run"] else ""
        print(f"  Email sent to {email_result['recipient']} {mode}")
    else:
        print(f"  Email FAILED: {email_result['error']}")
        errors.append(f"email: {email_result['error']}")

    # ── Step 3: Write to Google Sheets ────────────────────────────────────────
    print(f"\n[Phase 1] Writing to Master Orders sheet...")
    sheet_row    = None
    sheet_action = ""
    try:
        from write_to_sheets import write_order_result
        sheet_result = write_order_result(order, result, order_id=order_id)
        if sheet_result["ok"]:
            sheet_row    = sheet_result["row"]
            sheet_action = sheet_result["action"]
            print(f"  Sheet {sheet_action} — row {sheet_row}")
        else:
            print(f"  Sheet write FAILED: {sheet_result['reason']}")
            errors.append(f"sheets: {sheet_result['reason']}")
    except Exception as e:
        print(f"  Sheet write ERROR: {e}")
        errors.append(f"sheets: {e}")

    # ── Step 4: Send WhatsApp (Phase 2 — gated) ───────────────────────────────
    wa_sent    = False
    wa_dry_run = True
    wa_msg_id  = ""

    if _WHATSAPP_ENABLED:
        print(f"\n[Phase 2] Sending WhatsApp message...")
        phone_info = result.get("phone_normalized", {})
        intl_phone = phone_info.get("international", "")
        message    = result.get("customer_message", "")

        if intl_phone and message:
            from send_whatsapp_message import send_whatsapp_message
            wa_result  = send_whatsapp_message(intl_phone, message)
            wa_sent    = wa_result["sent"]
            wa_dry_run = wa_result["dry_run"]
            wa_msg_id  = wa_result.get("message_id", "")

            if wa_sent:
                mode = "(dry run)" if wa_dry_run else ""
                print(f"  WhatsApp sent to +{intl_phone} {mode}")
                # Update sheet with WhatsApp send info
                if sheet_row and not wa_dry_run:
                    try:
                        from write_to_sheets import write_order_result
                        write_order_result(order, result, send_result=wa_result,
                                           order_id=order_id)
                    except Exception:
                        pass
            else:
                print(f"  WhatsApp FAILED: {wa_result.get('error', '')}")
                errors.append(f"whatsapp: {wa_result.get('error', '')}")
        else:
            print("  WhatsApp skipped — no valid phone or message")
    else:
        print(f"\n[Phase 2] WhatsApp — not yet active (set WHATSAPP_PHASE2_ENABLED=true to enable)")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETE")
    print(f"  Status:        {status}")
    print(f"  Email:         {'sent' if email_result['sent'] else 'FAILED'}"
          f"{' (dry run)' if email_result.get('dry_run') else ''}")
    print(f"  Sheet row:     {sheet_row or 'not written'}")
    print(f"  WhatsApp:      {'sent' if wa_sent else 'pending Phase 2'}")
    if errors:
        print(f"  Errors:        {'; '.join(errors)}")
    print(f"{'='*60}\n")

    return {
        "status":        status,
        "risk_level":    risk,
        "escalation":    escalation,
        "email_sent":    email_result["sent"],
        "email_dry_run": email_result.get("dry_run", True),
        "whatsapp_sent": wa_sent,
        "sheet_row":     sheet_row,
        "sheet_action":  sheet_action,
        "errors":        errors,
        "result":        result,
    }


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_orders = [
        {
            "order_id":       "BS-TEST-001",
            "customer_name":  "Noor Al Rashidi",
            "phone":          "0551234567",
            "emirate":        "Dubai",
            "area":           "Jumeirah",
            "address":        "Villa 7, Street 10, Jumeirah 2",
            "maps_link":      "",
            "product":        "Hob Necklace",
            "colour":         "Gold",
            "quantity":       1,
            "unit_price":     59,
            "delivery_fee":   25,
            "total":          84,
            "payment_method": "Cash on Delivery",
            "payment_status": "Confirmed",
        },
        {
            "order_id":       "BS-TEST-002",
            "customer_name":  "Sara Mohammed",
            "phone":          "0501112233",
            "emirate":        "Sharjah",
            "area":           "Al Majaz",
            "address":        "Building 4, Apt 202",
            "product":        "Masha'Allah Bracelet",
            "colour":         "Silver",
            "quantity":       2,
            "unit_price":     79,
            "delivery_fee":   25,
            "total":          183,
            "payment_method": "Bank Transfer",
            "payment_status": "Pending",
        },
    ]

    for order in test_orders:
        summary = run_order_verification(order)
        print(f"Result: {summary['status']} | Email: {summary['email_sent']} | Row: {summary['sheet_row']}\n")
