# Directive: Mobile Validation

Layer 1 (Directive). Rules for accepting, normalising, and validating UAE mobile numbers.

## Goal

Ensure every order has a reachable UAE mobile number that the courier can call on delivery day.

## Accepted prefixes

050, 051, 052, 055, 056, 057, 058

## Steps

1. Strip all non-digit characters (spaces, dashes, brackets, `+`).
2. Detect and convert international format:
   - `971XXXXXXXXX` (12 digits) → prepend `0`, treat as local.
   - `00971XXXXXXXXX` (14 digits) → remove `00971`, prepend `0`.
3. Validate: must be exactly 10 digits starting with an accepted prefix.
4. Convert to E.164 format for WhatsApp API: `971` + digits 2–10.
5. If invalid → status = **High Risk / Do Not Pack**. Send `phone_invalid` message.

## Courier call confirmation

For every valid number, include a note asking the customer to confirm the number
can receive voice calls from the courier. Record in `Courier Call Confirmed` column.

## Execution

Call `execution/normalize_mobile.py` then `execution/validate_mobile.py`.
Never validate phone numbers manually.

## Examples

| Input | Result |
|---|---|
| `0501234567` | Valid — local: `0501234567`, intl: `971501234567` |
| `+971 50 123 4567` | Valid — normalised to same |
| `050 123 4567` | Valid |
| `050123` | Invalid — only 6 digits |
| `0601234567` | Invalid — prefix `060` not accepted |
| `04 123 4567` | Invalid — landline, not mobile |
