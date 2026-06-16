"""
test_module1.py  -  Module 1 test suite

Covers all 4 operational statuses and the main validation paths.
Run:  python tests/test_module1.py
"""

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "execution"))

from validate_order import validate_order, format_report

CASES = [
    {
        "title": "M1-01  Bank Transfer pending — Needs Correction",
        "order": {
            "customer_name": "Fatima Al Marri",    "phone":    "0501234567",
            "emirate":       "Dubai",               "area":     "JVC",
            "address":       "Villa 45, Al Manara Street, near Emirates Mall",
            "product":       "Masha'Allah Bracelet","colour":   "Gold",
            "quantity":      1,  "unit_price": 79,  "delivery_fee": 25, "total": 104,
            "payment_method": "Bank Transfer", "payment_status": "Pending",
        },
        "expect_status":    "Needs Correction",
        "expect_escalation": True,
    },
    {
        "title": "M1-02  Invalid phone — High Risk / Do Not Pack",
        "order": {
            "customer_name": "Ahmed Hassan",        "phone":    "050123",
            "emirate":       "Sharjah",             "area":     "Al Taawun",
            "address":       "Apartment 12, Building A, King Faisal Road",
            "product":       "Hob Necklace",        "colour":   "Silver",
            "quantity":      1,  "unit_price": 59,  "delivery_fee": 25, "total": 84,
            "payment_method": "Cash on Delivery", "payment_status": "Pending",
        },
        "expect_status":    "High Risk / Do Not Pack",
        "expect_escalation": True,
    },
    {
        "title": "M1-03  Wrong delivery fee — Needs Correction",
        "order": {
            "customer_name": "Sarah Al Zaabi",      "phone":    "0551234567",
            "emirate":       "Abu Dhabi",            "area":     "Khalifa City",
            "address":       "Villa 8, Street 12, near Carrefour",
            "product":       "Palestine Bracelet",  "colour":   "Silver",
            "quantity":      1,  "unit_price": 79,  "delivery_fee": 15, "total": 94,
            "payment_method": "Cash on Delivery", "payment_status": "Pending",
        },
        "expect_status":    "Needs Correction",
        "expect_escalation": True,
    },
    {
        "title": "M1-04  Missing address — High Risk / Do Not Pack",
        "order": {
            "customer_name": "Mariam Al Noor",      "phone":    "0561234567",
            "emirate":       "Ajman",               "area":     "",
            "address":       "",
            "product":       "Hob Necklace",        "colour":   "Gold",
            "quantity":      2,  "unit_price": 59,  "delivery_fee": 25, "total": 143,
            "payment_method": "Cash on Delivery", "payment_status": "Pending",
        },
        "expect_status":    "High Risk / Do Not Pack",
        "expect_escalation": True,
    },
    {
        "title": "M1-05  COD confirmed — Verified",
        "order": {
            "customer_name": "Noura Al Rashid",     "phone":    "0501234567",
            "emirate":       "Dubai",               "area":     "JVC",
            "address":       "Villa 10, Jumeirah Village Circle, Block 12",
            "product":       "Masha'Allah Bracelet","colour":   "Gold",
            "quantity":      1,  "unit_price": 79,  "delivery_fee": 25, "total": 104,
            "payment_method": "Cash on Delivery", "payment_status": "Pending",
            "customer_confirmed": True,
        },
        "expect_status":    "Verified",
        "expect_escalation": False,
    },
    {
        "title": "M1-06  COD not yet confirmed — Awaiting Confirmation",
        "order": {
            "customer_name": "Reem Al Blooshi",     "phone":    "0521234567",
            "emirate":       "Sharjah",             "area":     "Al Taawun",
            "address":       "Apartment 5, Al Noor Tower, opposite Clock Tower",
            "product":       "Qul Huwa Allah Ahad Bracelet", "colour": "Gold",
            "quantity":      1,  "unit_price": 79,  "delivery_fee": 25, "total": 104,
            "payment_method": "Cash on Delivery", "payment_status": "Pending",
            "customer_confirmed": False,
        },
        "expect_status":    "Awaiting Confirmation",
        "expect_escalation": False,
    },
]


def _safe_print(text):
    """Print with ASCII fallback so Windows cp1252 consoles don't crash."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def run():
    passed = 0
    full_log = []
    for c in CASES:
        result = validate_order(c["order"])
        ok_status = result["operational_status"] == c["expect_status"]
        ok_esc    = result["escalation"] == c["expect_escalation"]
        tag       = "PASS" if (ok_status and ok_esc) else "FAIL"
        if ok_status and ok_esc:
            passed += 1

        summary = (
            f"{tag}  {c['title']}\n"
            f"  expected : {c['expect_status']} / escalate={c['expect_escalation']}\n"
            f"  got      : {result['operational_status']} / escalate={result['escalation']}"
        )
        _safe_print("=" * 70)
        _safe_print(summary)
        full_log.append("=" * 70)
        full_log.append(summary)
        full_log.append("-" * 70)
        full_log.append(format_report(result))
        full_log.append("")

    _safe_print("=" * 70)
    _safe_print(f"MODULE 1 RESULT: {passed}/{len(CASES)} cases passed")
    full_log.append("=" * 70)
    full_log.append(f"MODULE 1 RESULT: {passed}/{len(CASES)} cases passed")

    # write full bilingual report to file
    log_path = Path(__file__).resolve().parent / "test_module1_last_run.txt"
    log_path.write_text("\n".join(full_log), encoding="utf-8")
    _safe_print(f"Full report saved to {log_path}")

    return passed == len(CASES)


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
