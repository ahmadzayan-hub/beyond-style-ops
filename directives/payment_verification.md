# Directive: Payment Verification

Layer 1 (Directive). Rules for verifying payment method and status before packing.

## Goal

Ensure the business is never left with an unpaid order or a courier collecting
cash for an order where the customer expected to pay in advance.

## Accepted payment methods

| Method | Proof required before packing? |
|---|---|
| Cash on Delivery | No — courier collects at door |
| Bank Transfer | Yes — screenshot of transfer |
| Debit Card | Yes — confirmed payment status |

## Rules

1. Payment method must be one of the three accepted methods.
2. `Bank Transfer` and `Debit Card`: status must be `Confirmed` before packing.
   If status is `Pending` → **Needs Correction**. Send `payment_proof_request`.
3. `Cash on Delivery`: no proof required upfront, but customer must confirm
   the order before packing.
4. Never assume payment is confirmed without seeing proof.
5. Never dispatch a COD order if the customer has not replied CONFIRM.

## Execution

Call `execution/validate_payment.py`.

## Edge cases

- Screenshot shared but unreadable → treat as not confirmed.
- Amount on screenshot does not match order total → treat as not confirmed.
  Escalate to owner.
- Customer claims card was charged but status is Pending → escalate to owner,
  do not pack until confirmed.
