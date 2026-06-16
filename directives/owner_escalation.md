# Directive: Owner Escalation

Layer 1 (Directive). Rules for alerting the owner when an order requires human
review before any action is taken.

## Goal

The owner must always have a clear, plain-language summary of what is wrong and
exactly what they need to do — no code, no jargon.

## When to escalate

- Status = `High Risk / Do Not Pack`
- Status = `Needs Correction`
- Any time the agent cannot determine the correct next step with confidence.

## Escalation report contents

1. Timestamp (UTC)
2. Customer name, phone, product, location
3. Operational Status and Risk Level
4. Numbered list of every issue found
5. Exact next action (one sentence)
6. Clear warning: DO NOT pack or dispatch until resolved.

## Format rules

- Plain language. No Python, no JSON, no technical jargon.
- Keep it short enough to read in 30 seconds.
- If there is only one issue, do not number it.
- Always end with the next action.

## Execution

Call `execution/create_owner_escalation.py`.

## Delivery channel

Until a notification integration is built:
- Print the escalation report to console.
- Log it to the Google Sheets `Internal Notes` column (if Sheets is connected).

Future: send via WhatsApp to the owner's number (separate from customer messages),
email, or Slack webhook — set these up in `.env` when ready.

## What the owner does with an escalation

1. Read the numbered issues.
2. Contact the customer if needed.
3. Update the relevant field in the order.
4. Re-run verification.
5. Only approve packing after status = Verified.
