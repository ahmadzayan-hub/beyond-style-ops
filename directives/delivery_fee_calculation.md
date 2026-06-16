# Directive: Delivery Fee Calculation

Layer 1 (Directive). Rules for looking up and verifying the correct delivery fee.

## Goal

Make sure every order carries the correct AED delivery fee before the customer
confirms, so there are no surprises at the door.

## Current policy (effective 2026-05-31)

Standard UAE delivery fee: **AED 25** (flat rate, all emirates, Halan / approved courier).
Express add-on: +AED 25 (only when owner approves express delivery).

Source: Beyond Style Delivery Policy sheet, 01/06/2026 update.
Do NOT use AED 30.

## Fee lookup

1. Load `data/delivery_fees.json`.
2. Match emirate (case-insensitive).
3. Check for area override first; fall back to emirate default.
4. Add express surcharge if `express=True`.

## Validation

- If the fee in the order does not match the policy fee → **Needs Correction**.
  Recalculate, update total, send `correction_fee` message.
- If the emirate is not in the fee table → **High Risk / Do Not Pack**.
  Add the real fee to `data/delivery_fees.json` and re-run.
- Fees marked `placeholder` in the JSON file must be confirmed by the owner
  before using them in production orders.

## Execution

Call `execution/calculate_delivery_fee.py`.

## Editing fees

To add or correct a fee, edit `data/delivery_fees.json` directly.
Mark confirmed fees as `"status": "confirmed"` and placeholder estimates as
`"status": "placeholder"`.
