"""
test_verification.py  -  reproduces the three real Beyond Style test cases and
asserts the verifier returns the expected outcome. Run:  python tests/test_verification.py
"""

import sys
from pathlib import Path

# allow importing from execution/ when run from project root or tests/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "execution"))

from verify_order import verify_order, format_report

CASES = [
    {
        "title": "Test 1 - Complete order, Bank Transfer pending (Dubai JVC)",
        "order": {
            "customer_name": "Fatima Al Marri", "phone": "0501234567",
            "emirate": "Dubai", "area": "JVC",
            "address": "Villa 45, Al Manara Street, near Emirates Mall",
            "product": "Gold Layered Chain Necklace", "colour": "Gold", "quantity": 1,
            "unit_price": 89, "delivery_fee": 15, "total": 104,
            "payment_method": "Bank Transfer", "payment_status": "Pending",
        },
        "expect_status": "Needs Correction",
        "expect_escalation": True,
    },
    {
        "title": "Test 2 - Invalid phone (Sharjah Al Taawun, COD)",
        "order": {
            "customer_name": "Ahmed Hassan", "phone": "050123",
            "emirate": "Sharjah", "area": "Al Taawun",
            "address": "Apartment 12, Building A, King Faisal Road",
            "product": "Pearl Drop Earrings", "colour": "Pearl", "quantity": 2,
            "unit_price": 65, "delivery_fee": 20, "total": 150,
            "payment_method": "Cash on Delivery", "payment_status": "Pending",
        },
        "expect_status": "High Risk / Do Not Pack",
        "expect_escalation": True,
    },
    {
        "title": "Test 3 - Emirate change Dubai->Sharjah, fee recalculation",
        "order": {
            "customer_name": "Fatima Al Marri", "phone": "0501234567",
            "emirate": "Sharjah", "area": "Al Taawun",
            "address": "Villa 23, Al Wasl Street, near Clock Tower",
            "product": "Gold Layered Chain Necklace", "colour": "Gold", "quantity": 1,
            "unit_price": 89, "delivery_fee": 15, "total": 104,   # old Dubai fee/total
            "payment_method": "Bank Transfer", "payment_status": "Pending",
        },
        "expect_status": "Needs Correction",
        "expect_escalation": True,
    },
]


def run():
    passed = 0
    for c in CASES:
        result = verify_order(c["order"])
        ok_status = result["operational_status"] == c["expect_status"]
        ok_esc = result["escalation"] == c["expect_escalation"]
        status = "PASS" if (ok_status and ok_esc) else "FAIL"
        if ok_status and ok_esc:
            passed += 1
        print("=" * 70)
        print(f"{status}  {c['title']}")
        print(f"  expected: {c['expect_status']} / escalate={c['expect_escalation']}")
        print(f"  got:      {result['operational_status']} / escalate={result['escalation']}")
        print("-" * 70)
        print(format_report(result))
        print()
    print("=" * 70)
    print(f"RESULT: {passed}/{len(CASES)} cases passed")
    return passed == len(CASES)


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
