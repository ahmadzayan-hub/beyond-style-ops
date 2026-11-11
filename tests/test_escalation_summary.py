"""
test_escalation_summary.py  -  unit checks for the daily owner escalation summary.
Run:  python tests/test_escalation_summary.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "execution"))

from daily_escalation_summary import summarize_high_risk_orders

ORDER_A = {"customer_name": "Fatima Al Marri", "product": "Gold hoop earrings"}
ORDER_B = {"customer_name": "Sara Ali", "product": "Silver chain"}
ORDER_C = {"customer_name": "Hind Saeed", "product": "Pearl bracelet"}

RESULT_BLOCK = {
    "operational_status": "High Risk / Do Not Pack",
    "risk_level": "High",
    "missing_or_risky": ["Address is missing", "Phone number invalid"],
}
RESULT_HIGH_ONLY = {
    "operational_status": "Needs Correction",
    "risk_level": "High",
    "missing_or_risky": ["Quantity must be greater than zero"],
}
RESULT_VERIFIED = {
    "operational_status": "Verified",
    "risk_level": "Low",
    "missing_or_risky": [],
}

CASES = [
    ("no orders -> count 0 and empty report",
     [], 0, ""),
    ("only verified orders -> nothing flagged",
     [(ORDER_C, RESULT_VERIFIED)], 0, ""),
    ("status Do Not Pack is flagged",
     [(ORDER_A, RESULT_BLOCK)], 1, "Fatima Al Marri"),
    ("risk level High is flagged even when status is Needs Correction",
     [(ORDER_B, RESULT_HIGH_ONLY)], 1, "Sara Ali"),
    ("mixed batch keeps only flagged orders in input order",
     [(ORDER_A, RESULT_VERIFIED), (ORDER_B, RESULT_BLOCK), (ORDER_C, RESULT_HIGH_ONLY)], 2, None),
]

failures = 0
for name, pairs, expected_count, must_contain in CASES:
    out = summarize_high_risk_orders(pairs, "2026-10-27")
    ok = out["count"] == expected_count
    if must_contain is not None:
        ok = ok and (must_contain in out["report"] or expected_count == 0)
    if expected_count == 0:
        ok = ok and out["report"] == "" and out["orders"] == []
    if name.startswith("mixed"):
        ok = ok and [o["customer"] for o in out["orders"]] == ["Sara Ali", "Hind Saeed"]
    if name.startswith("status Do Not Pack"):
        ok = ok and out["orders"][0]["reasons"] == ["Address is missing", "Phone number invalid"]
    print(("PASS" if ok else "FAIL"), "-", name)
    if not ok:
        failures += 1
        print(out)

print()
print(f"ESCALATION SUMMARY RESULT: {len(CASES) - failures}/{len(CASES)} cases passed")
sys.exit(1 if failures else 0)
