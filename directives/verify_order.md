# Directive: Verify Order

Layer 1 (Directive). This is the SOP for verifying a Beyond Style order before
packing and courier handover. It is written in plain language. The agent (Layer 2)
reads this, then calls the execution scripts (Layer 3) to do the work.

## Goal

Make sure an order is correct, complete, and confirmed before any packing happens,
so the business never wastes effort on a bad order or a failed delivery.

## When to run

Run this whenever a new order arrives through WhatsApp, Instagram, TikTok, or a form,
and whenever a customer changes any detail of an existing order (especially the
delivery area, which changes the fee).

## Inputs

A single order with these 13 fields:

1. customer_name
2. phone (UAE mobile)
3. emirate
4. area
5. address (street / villa / apartment, a landmark is fine)
6. product (must match the catalogue)
7. colour
8. quantity
9. unit_price (AED)
10. delivery_fee (AED)
11. total (AED)
12. payment_method (Cash on Delivery, Bank Transfer, or Card)
13. payment_status (Pending or Confirmed)

Optional: `customer_confirmed` (true once the customer has confirmed the details).

## Tool to use

Call `execution/verify_order.py` with the order. It runs every rule and returns the
eight sections below. Do not re-implement these checks by hand; the script is the
single source of truth so the result is identical every time.

```
from verify_order import verify_order, format_report
result = verify_order(order_dict)
print(format_report(result))
```

## The rules the script applies

- **All 13 fields must be present.** Any missing field is a hard stop.
- **Phone must be a valid UAE mobile** (10 digits, 05X + 7 more). Invalid phone is a
  hard stop, because the courier cannot deliver without it. This is the single most
  important check.
- **Product must be in the catalogue**, and the colour must be one we offer.
- **Delivery fee must match the policy** for that emirate and area
  (`data/delivery_fees.json`). If the area changed, the fee is recalculated.
- **Total must equal** unit price times quantity, plus the correct delivery fee.
- **Bank Transfer and Card need payment proof** before dispatch. Cash on Delivery is
  collected by the courier, so it does not need proof up front.
- **The customer must confirm the details** before an order is fully verified.

## Outputs (the eight sections)

1. **Data Check** - which fields are present and valid
2. **Missing or Risky Info** - every problem found, in plain language
3. **Customer Message Draft** - the right WhatsApp message to send
4. **Operational Status** - one of: Verified, Awaiting Confirmation, Needs Correction,
   High Risk / Do Not Pack
5. **Risk Level** - Low, Medium, or High
6. **Next Action** - the exact step for the owner
7. **Tracker Update** - what to record
8. **Escalation** - yes or no, with the reason

## How to decide status (the script does this for you)

- Any missing field or invalid phone, or an emirate with no configured fee
  -> **High Risk / Do Not Pack**, escalate.
- A fixable mismatch (wrong fee, wrong total, unrecognised product/colour, or payment
  proof still needed) -> **Needs Correction**, escalate.
- Everything correct but the customer has not confirmed yet
  -> **Awaiting Confirmation**, no escalation, send the confirmation message.
- Everything correct and confirmed -> **Verified**, prepare for dispatch.

## Edge cases

- **Area changed after the order was placed.** Re-run this directive. The fee and
  total will be recalculated and the customer asked to approve the new total.
- **Emirate not yet in the fee table.** The script returns High Risk so you do not
  guess a fee. Add the real fee to `data/delivery_fees.json` and re-run.
- **Placeholder fee.** Fees marked placeholder still produce a result but the script
  warns you to confirm the real value. Replace placeholders with confirmed values.

## What to do with the result

- If escalation is YES, the owner reviews before anything is packed.
- Send the drafted customer message through the normal channel (the agent does not
  message customers directly).
- Never pack an order whose status is Needs Correction or High Risk / Do Not Pack.

## Learnings

When you discover a new rule, a new product, a corrected fee, or a new edge case,
update this directive and the relevant data file so the knowledge is not lost.
