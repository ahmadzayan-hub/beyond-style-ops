# Directive: Status and Risk Logic

Layer 1 (Directive). Defines how verification status and risk level are assigned.

## Status values (use exactly as written)

| Status | Meaning |
|---|---|
| `Verified` | All checks pass, customer confirmed. Safe to pack. |
| `Awaiting Confirmation` | All checks pass but customer has not replied CONFIRM yet. |
| `Needs Correction` | A fixable problem was found. Do not pack. |
| `High Risk / Do Not Pack` | A blocking problem was found. Do not pack. Escalate. |

## Status decision tree

```
Any missing field OR invalid phone OR unknown emirate?
  → High Risk / Do Not Pack  (escalate=YES)

Wrong fee OR wrong total OR unknown product OR
payment proof missing OR unrecognised colour?
  → Needs Correction  (escalate=YES)

Everything correct but customer_confirmed = False?
  → Awaiting Confirmation  (escalate=No)

Everything correct AND customer_confirmed = True?
  → Verified  (escalate=No)
```

## Risk levels

| Level | Conditions |
|---|---|
| Low | Verified order. All data valid, payment confirmed or COD, customer confirmed. |
| Medium | Minor issue — missing maps link, COD awaiting confirmation, placeholder fee. |
| High | Any blocking issue: invalid phone, missing field, unrecognised emirate, missing address, payment proof outstanding, wrong total. |

## Escalation rule

Escalation = YES whenever status is `Needs Correction` or `High Risk / Do Not Pack`.
The owner must review before anything is packed.

## Execution

Status and risk are computed inside `execution/validate_order.py`.
`execution/risk_score_order.py` handles the risk level calculation.
