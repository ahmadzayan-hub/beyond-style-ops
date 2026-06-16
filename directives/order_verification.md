# Directive: Order Verification (Module 1)

Layer 1 (Directive). Master SOP for verifying a Beyond Style UAE order before
packing and courier handover.

## Goal

Guarantee every order is complete, correct, and confirmed before a single item
is packed, so the business never wastes effort on a bad order or a failed delivery.

## When to run

- Every new order from WhatsApp, Instagram, TikTok, online forms, Noon, or Amazon.
- Every time a customer changes any detail (product, address, quantity) on an existing order.

## Inputs — 13 mandatory fields

| # | Field | Notes |
|---|---|---|
| 1 | customer_name | Full name |
| 2 | phone | UAE mobile, 10 digits |
| 3 | emirate | One of 7 known emirates |
| 4 | area | District / neighbourhood |
| 5 | address | Building / villa + street + landmark |
| 6 | product | Must match product catalogue |
| 7 | colour | Must match offered colours (if confirmed) |
| 8 | quantity | Integer ≥ 1 |
| 9 | unit_price | AED, must match catalogue price |
| 10 | delivery_fee | AED, must match policy |
| 11 | total | AED = (unit_price × qty) + delivery_fee |
| 12 | payment_method | Cash on Delivery \| Bank Transfer \| Debit Card |
| 13 | payment_status | Pending \| Confirmed |

Optional: `maps_link` (Google Maps / WhatsApp live location),
`customer_confirmed` (bool — True once customer has replied CONFIRM).

## Execution

Call `execution/validate_order.py`. Do not re-implement checks by hand.

```python
from validate_order import validate_order, format_report
result = validate_order(order_dict)
print(format_report(result))
```

## Sub-modules called

1. `normalize_mobile.py` + `validate_mobile.py`
2. `validate_location.py`
3. `calculate_delivery_fee.py`
4. `calculate_order_total.py`
5. `validate_payment.py`
6. `risk_score_order.py`
7. `generate_whatsapp_message.py`

## Output — 8 sections

1. Data Check
2. Missing or Risky Info
3. Customer Message Draft (bilingual EN + Gulf Arabic)
4. Operational Status
5. Risk Level
6. Next Action
7. Tracker Update
8. Escalation Required

## Hard rules

- Do not invent missing data.
- Do not assume payment is confirmed without proof.
- Do not recommend packing unless status = Verified.
- If anything is unclear, freeze dispatch and escalate to the owner.
