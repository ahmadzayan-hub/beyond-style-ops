"""
test_directives.py  -  per-directive smoke coverage.

One block per Layer 1 directive, exercising the execution script that directive
names, with the directive's own documented examples and rules. Pure functions
only: tracker_writeback is covered up to build_tracker_update (the gspread
writer needs credentials and is not run here), and customer_whatsapp_messages
is covered for text generation only (nothing is sent).

Run:  python tests/test_directives.py
"""

import sys
from pathlib import Path

# Templates contain emoji and Arabic; keep the PASS/FAIL log readable on any console.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "execution"))

from normalize_mobile import normalize_mobile
from validate_mobile import validate_mobile
from validate_location import validate_location
from calculate_delivery_fee import calculate_delivery_fee
from calculate_order_total import calculate_order_total
from validate_payment import validate_payment
from risk_score_order import risk_score_order
from generate_whatsapp_message import generate_whatsapp_message, TEMPLATES
from create_owner_escalation import create_owner_escalation
from build_tracker_update import build_tracker_update
from calculate_total import lookup_product, compute_total
from validate_order import validate_order

failures = 0
total = 0


def check(directive: str, name: str, ok: bool, detail=None):
    global failures, total
    total += 1
    print(("PASS" if ok else "FAIL"), "-", f"[{directive}]", name)
    if not ok:
        failures += 1
        if detail is not None:
            print("      ", detail)


# --------------------------------------------------------------------------
# mobile_validation.md  ->  normalize_mobile.py + validate_mobile.py
# --------------------------------------------------------------------------
D = "mobile_validation"
for raw in ["0501234567", "+971 50 123 4567", "050 123 4567", "00971501234567"]:
    r = normalize_mobile(raw)
    check(D, f"{raw!r} is valid and normalises to 971501234567",
          r["valid"] and r["local"] == "0501234567" and r["international"] == "971501234567", r)
for raw, why in [("050123", "6 digits"), ("0601234567", "prefix 060"), ("04 123 4567", "landline"),
                 ("", "empty"), (None, "None")]:
    r = normalize_mobile(raw)
    check(D, f"{raw!r} is rejected ({why})", not r["valid"] and r["international"] == "" and bool(r["reason"]), r)
v = validate_mobile("0551234567")
check(D, "valid number carries the courier-call reminder",
      v["valid"] and "voice calls" in v["courier_note"] and v["international"] == "971551234567", v)
check(D, "invalid number carries no courier note", validate_mobile("050123")["courier_note"] == "")

# --------------------------------------------------------------------------
# location_validation.md  ->  validate_location.py
# --------------------------------------------------------------------------
D = "location_validation"
r = validate_location("Dubai", "JVC", "Villa 45, Al Manara Street, near Emirates Mall", "https://maps.app.goo.gl/x")
check(D, "complete location with maps link is valid and Low risk",
      r["valid"] and r["risk_level"] == "Low" and not r["maps_requested"], r)
r = validate_location("Dubai", "JVC", "Villa 45, Al Manara Street, near Emirates Mall")
check(D, "missing maps link -> Medium risk and maps requested",
      not r["valid"] and r["risk_level"] == "Medium" and r["maps_requested"]
      and any("Maps" in i for i in r["issues"]), r)
r = validate_location("Dubai", "JVC", "Villa 45", "https://maps.app.goo.gl/x")
check(D, "address under 10 chars -> too short, Medium (fixable)",
      r["risk_level"] == "Medium" and any("too short" in i for i in r["issues"]), r)
r = validate_location("Manchester", "City", "10 Downing Street, near the park", "https://maps.app.goo.gl/x")
check(D, "unknown emirate -> High",
      r["risk_level"] == "High" and any("not recognised" in i for i in r["issues"]), r)
r = validate_location("", "", "", None)
check(D, "every field missing -> High with one issue per field",
      r["risk_level"] == "High" and sum("missing" in i for i in r["issues"]) == 3, r)
for em in ["Dubai", "Sharjah", "Ajman", "Umm Al Quwain", "Ras Al Khaimah", "Fujairah", "Abu Dhabi"]:
    r = validate_location(em, "Area", "Building 1, Street 2, near landmark", "x")
    check(D, f"emirate {em} is recognised", r["valid"], r)

# --------------------------------------------------------------------------
# delivery_fee_calculation.md  ->  calculate_delivery_fee.py
# --------------------------------------------------------------------------
D = "delivery_fee_calculation"
for em in ["Dubai", "Sharjah", "Ajman", "Umm Al Quwain", "Ras Al Khaimah", "Fujairah", "Abu Dhabi"]:
    r = calculate_delivery_fee(em)
    check(D, f"{em}: flat AED 25, confirmed (policy 2026-05-31)",
          r["found"] and r["fee"] == 25 and r["total_fee"] == 25 and r["confirmed"] and r["reason"] == "", r)
r = calculate_delivery_fee("dubai", "jvc")
check(D, "emirate match is case-insensitive and superseded JVC override is gone (AED 25, not 15)",
      r["found"] and r["fee"] == 25 and r["source"] == "Dubai (default)", r)
r = calculate_delivery_fee("Dubai", express=True)
check(D, "express adds AED 25 surcharge -> total 50", r["express_surcharge"] == 25 and r["total_fee"] == 50, r)
r = calculate_delivery_fee("Muscat")
check(D, "emirate not in table -> not found with actionable reason",
      not r["found"] and r["fee"] is None and "not in the delivery fee table" in r["reason"], r)
check(D, "AED 30 is never returned for any emirate",
      all(calculate_delivery_fee(e)["fee"] != 30 for e in ["Dubai", "Sharjah", "Abu Dhabi"]))

# --------------------------------------------------------------------------
# payment_verification.md  ->  validate_payment.py
# --------------------------------------------------------------------------
D = "payment_verification"
r = validate_payment("Cash on Delivery", "Pending")
check(D, "COD pending: no proof required, can pack after confirmation",
      r["valid"] and not r["proof_required"] and r["can_pack"], r)
r = validate_payment("Bank Transfer", "Pending")
check(D, "Bank Transfer pending -> blocked, screenshot requested",
      not r["can_pack"] and r["proof_required"] and any("screenshot" in i for i in r["issues"]), r)
r = validate_payment("Bank Transfer", "Confirmed")
check(D, "Bank Transfer confirmed -> can pack", r["valid"] and r["can_pack"], r)
r = validate_payment("Debit Card", "confirmed")
check(D, "Debit Card confirmed (status case-insensitive) -> can pack", r["valid"] and r["proof_required"], r)
r = validate_payment("Debit Card", "Pending")
check(D, "Debit Card pending -> blocked", not r["can_pack"], r)
r = validate_payment("Crypto", "Confirmed")
check(D, "unknown method -> rejected, lists accepted methods",
      not r["valid"] and "not accepted" in r["issues"][0] and "Cash on Delivery" in r["issues"][0], r)
r = validate_payment("", "Confirmed")
check(D, "missing method -> rejected", not r["valid"] and "missing" in r["issues"][0], r)
r = validate_payment("Bank Transfer", "")
check(D, "missing status -> rejected, proof still flagged as required", not r["valid"] and r["proof_required"], r)

# --------------------------------------------------------------------------
# product_catalogue_check.md  ->  calculate_total.py (lookup_product, compute_total)
# --------------------------------------------------------------------------
D = "product_catalogue_check"
p = lookup_product("gold layered chain necklace")
check(D, "catalogue lookup is case-insensitive and returns price + colours",
      p["found"] and p["unit_price"] == 89 and "Gold" in p["colours"], p)
p = lookup_product("Diamond Tiara")
check(D, "unknown product -> not found, owner must add/correct",
      not p["found"] and "not in the catalogue" in p["reason"], p)
check(D, "compute_total 89 x 1 + 15 = 104", compute_total(89, 1, 15)["total"] == 104)
check(D, "compute_total 65 x 2 + 20 = 150", compute_total(65, 2, 20)["total"] == 150)
check(D, "compute_total rejects zero quantity", not compute_total(89, 0, 25)["ok"])
check(D, "compute_total rejects non-numeric price", not compute_total("free", 1, 25)["ok"])
t = calculate_order_total(89, 1, 25)
check(D, "calculate_order_total 89 x 1 + 25 = 114", t["ok"] and t["total"] == 114 and t["line_total"] == 89, t)
check(D, "calculate_order_total rejects negative delivery fee", not calculate_order_total(89, 1, -5)["ok"])

# --------------------------------------------------------------------------
# status_and_risk_logic.md  ->  risk_score_order.py (+ validate_order decision tree)
# --------------------------------------------------------------------------
D = "status_and_risk_logic"
check(D, "no issues -> Low", risk_score_order([])["risk_level"] == "Low")
check(D, "'missing' issue -> High", risk_score_order(["Address is missing"])["risk_level"] == "High")
check(D, "'invalid' issue -> High", risk_score_order(["Phone number invalid"])["risk_level"] == "High")
check(D, "'not recognised' issue -> High",
      risk_score_order(["Emirate 'X' is not recognised."])["risk_level"] == "High")
check(D, "blocking flag -> High even with a minor issue",
      risk_score_order(["Maps link not provided"], blocking=True)["risk_level"] == "High")
check(D, "maps-link-only issue -> Medium",
      risk_score_order(["Google Maps link / live location not provided"])["risk_level"] == "Medium")
check(D, "placeholder fee -> Medium",
      risk_score_order(["Fee for Dubai (default) is a placeholder"])["risk_level"] == "Medium")
r = risk_score_order(["a", "b"])
check(D, "risk_score counts issues and echoes them as factors",
      r["risk_score"] == 2 and r["risk_factors"] == ["a", "b"], r)

BASE_ORDER = {
    "customer_name": "Fatima Al Marri", "phone": "0501234567",
    "emirate": "Dubai", "area": "JVC",
    "address": "Villa 45, Al Manara Street, near Emirates Mall",
    "maps_link": "https://maps.app.goo.gl/x",
    "product": "Gold Layered Chain Necklace", "colour": "Gold", "quantity": 1,
    "unit_price": 89, "delivery_fee": 25, "total": 114,
    "payment_method": "Cash on Delivery", "payment_status": "Pending",
}
r = validate_order(dict(BASE_ORDER))
check(D, "decision tree: all correct, not confirmed -> Awaiting Confirmation, no escalation",
      r["operational_status"] == "Awaiting Confirmation" and not r["escalation"], r)
r = validate_order({**BASE_ORDER, "customer_confirmed": True})
check(D, "decision tree: all correct and confirmed -> Verified, Low",
      r["operational_status"] == "Verified" and r["risk_level"] == "Low" and not r["escalation"], r)
r = validate_order({**BASE_ORDER, "phone": "050123"})
check(D, "decision tree: invalid phone -> High Risk / Do Not Pack, escalate",
      r["operational_status"] == "High Risk / Do Not Pack" and r["escalation"], r)
r = validate_order({**BASE_ORDER, "delivery_fee": 30, "total": 119})
check(D, "decision tree: wrong fee (AED 30) -> Needs Correction, escalate",
      r["operational_status"] == "Needs Correction" and r["escalation"], r)
r = validate_order({**BASE_ORDER, "payment_method": "Bank Transfer"})
check(D, "decision tree: Bank Transfer pending -> Needs Correction, escalate",
      r["operational_status"] == "Needs Correction" and r["escalation"], r)
r = validate_order({**BASE_ORDER, "address": ""})
check(D, "decision tree: missing address -> High Risk / Do Not Pack",
      r["operational_status"] == "High Risk / Do Not Pack", r)

# --------------------------------------------------------------------------
# customer_whatsapp_messages.md  ->  generate_whatsapp_message.py (text only)
# --------------------------------------------------------------------------
D = "customer_whatsapp_messages"
EXPECTED_TYPES = {"confirm_order", "correction_fee", "payment_proof_request",
                  "phone_invalid", "location_request", "dispatch_confirmed"}
check(D, "all six documented message types exist", EXPECTED_TYPES == set(TEMPLATES), sorted(TEMPLATES))
for mt in sorted(EXPECTED_TYPES):
    m = generate_whatsapp_message(mt, BASE_ORDER)
    ok = (m["ok"] and m["en"] and m["ar"] and "Beyond Style UAE" in m["en"]
          and m["combined"].startswith(m["en"]) and m["combined"].endswith(m["ar"]))
    check(D, f"{mt}: bilingual EN + AR, branded, combined in order", bool(ok), m["reason"])
m = generate_whatsapp_message("confirm_order", BASE_ORDER)
check(D, "confirm_order carries the total breakdown and CONFIRM instruction",
      "AED 114" in m["en"] and "AED 89" in m["en"] and "CONFIRM" in m["en"] and "Fatima Al Marri" in m["ar"], m["en"])
m = generate_whatsapp_message("confirm_order", {**BASE_ORDER, "maps_link": ""})
check(D, "missing maps link -> placeholder, never invented", "[Share your Google Maps" in m["en"], m["en"])
m = generate_whatsapp_message("confirm_order", {**BASE_ORDER, "colour": ""})
check(D, "empty colour omits the colour parenthesis", "(Gold)" not in m["en"], m["en"])
m = generate_whatsapp_message("refund_offer", BASE_ORDER)
check(D, "unknown type -> ok=False with the allowed list", not m["ok"] and "confirm_order" in m["reason"], m)
m = generate_whatsapp_message("confirm_order", {})
check(D, "empty fields never crash: 'Valued Customer' default is substituted",
      m["ok"] and "Valued Customer" in m["en"], m["reason"])
m = generate_whatsapp_message("phone_invalid", {})
check(D, "phone_invalid with no fields still renders both languages", m["ok"] and m["en"] and m["ar"], m["reason"])

# --------------------------------------------------------------------------
# owner_escalation.md  ->  create_owner_escalation.py
# --------------------------------------------------------------------------
D = "owner_escalation"
res = validate_order({**BASE_ORDER, "phone": "050123", "address": ""})
e = create_owner_escalation(BASE_ORDER, res)
report = e["report"]
check(D, "escalated order -> required with every issue as a reason",
      e["required"] and e["reasons"] == res["missing_or_risky"] and len(e["reasons"]) >= 2, e)
check(D, "report contains timestamp, customer, phone, product, location, status, risk",
      all(s in report for s in ["UTC", "Fatima Al Marri", "0501234567", "Gold Layered Chain Necklace",
                                "JVC, Dubai", "High Risk / Do Not Pack", "Risk     : High"]), report)
check(D, "report numbers the issues and ends with the DO NOT pack warning and next action",
      "  1. " in report and "  2. " in report and "DO NOT pack or dispatch" in report and "Next action:" in report,
      report)
check(D, "report is plain language (no JSON/code)", "{" not in report and "def " not in report, report)
e = create_owner_escalation(BASE_ORDER, validate_order({**BASE_ORDER, "customer_confirmed": True}))
check(D, "verified order -> no escalation, empty report",
      not e["required"] and e["report"] == "" and e["reasons"] == [], e)

# --------------------------------------------------------------------------
# tracker_writeback.md  ->  build_tracker_update.py (mapping only; no Sheets I/O)
# --------------------------------------------------------------------------
D = "tracker_writeback"
res = validate_order({**BASE_ORDER, "payment_method": "Bank Transfer"})
u = build_tracker_update(BASE_ORDER, res)
m = u["mapping"]
check(D, "mapping uses the sheet's exact column headers",
      u["ok"] and m.get("Customer Name") == "Fatima Al Marri" and m.get("Mobile Number") == "0501234567"
      and m.get("WhatsApp Number") == "971501234567" and m.get("Total Amount") == 114, m)
check(D, "status, risk and escalation columns reflect the verification result",
      m.get("Critical Data Status") == "Needs Correction" and m.get("Risk Status") == res["risk_level"]
      and m.get("Escalation Required") == "YES" and "screenshot" in m.get("Escalation Reason", ""), m)
check(D, "Last Updated is stamped in UTC", m.get("Last Updated", "").endswith("UTC"), m.get("Last Updated"))
check(D, "no WhatsApp columns without a send result", "WhatsApp Message Sent" not in m)
u = build_tracker_update(BASE_ORDER, res,
                         {"sent": True, "timestamp": "2026-11-03 10:00 UTC", "message_id": "wamid.X"})
m = u["mapping"]
check(D, "send result fills the four WhatsApp columns",
      m.get("WhatsApp Message Sent") == "Yes" and m.get("WhatsApp Message Type") == res.get("message_type", "")
      and m.get("WhatsApp Sent Time") == "2026-11-03 10:00 UTC" and m.get("Meta Message ID") == "wamid.X", m)
u = build_tracker_update(BASE_ORDER, validate_order({**BASE_ORDER, "customer_confirmed": True}))
check(D, "verified order -> Escalation Required 'No' and empty reason",
      u["mapping"].get("Escalation Required") == "No" and u["mapping"].get("Escalation Reason") == "", u["mapping"])

print()
print(f"DIRECTIVE SMOKE RESULT: {total - failures}/{total} cases passed")
sys.exit(1 if failures else 0)
