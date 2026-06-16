# Directive: Customer WhatsApp Messages

Layer 1 (Directive). Rules for generating and handling bilingual WhatsApp messages.

## Goal

Every message sent to a customer must be accurate, bilingual (English + Gulf Arabic),
polite, and match the exact verification scenario — never copied from the wrong template.

## Message types

| Type | When to use |
|---|---|
| `confirm_order` | All fields valid, awaiting CONFIRM from customer |
| `correction_fee` | Delivery fee or total was updated — needs re-confirmation |
| `payment_proof_request` | Bank Transfer / Debit Card — payment screenshot needed |
| `phone_invalid` | Cannot verify a valid UAE mobile number |
| `location_request` | Missing or unclear address / maps link |
| `dispatch_confirmed` | Order verified, going to courier |

## Rules

1. Always generate bilingual messages (English first, Arabic below a divider).
2. Arabic uses simplified Gulf dialect — formal MSA is not used.
3. Always show the exact product name, colour, quantity, unit price, delivery fee,
   and total — never use placeholders in messages sent to customers.
4. For `payment_proof_request`, state the exact payment method and AED amount.
5. The agent never sends messages to customers. It hands the draft to the owner.
6. The owner reviews and sends through WhatsApp Business / Meta Business Suite.
7. When WhatsApp API credentials are set in `.env`, `send_whatsapp_message.py`
   can auto-send after owner review.

## Execution

Call `execution/generate_whatsapp_message.py`.

## Auto-send logic (when API is live)

- Status = Awaiting Confirmation → auto-send `confirm_order`.
- Status = Needs Correction (fixable) → auto-send relevant correction message.
- Status = High Risk → do NOT auto-send. Alert owner only.
- After sending, record message ID, type, and timestamp in Google Sheets.

## 24-hour hold rule

Every confirmation message tells the customer the item is held for 24 hours.
If no CONFIRM reply within 24 hours, escalate to owner for a follow-up decision.
