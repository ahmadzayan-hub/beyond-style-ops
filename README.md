# Beyond Style Order Verification Agent

A starter project for verifying Beyond Style UAE orders before packing and courier
handover. It is built on a 3-layer architecture so the business rules stay consistent
and reliable instead of being re-checked by hand each time.

## What it does

Give it an order with the 13 standard fields and it returns an eight-section result:
what is present and valid, what is missing or risky, a ready-to-send WhatsApp message,
the operational status, the risk level, the next action, what to record, and whether
to escalate to the owner. The order checks (phone format, delivery fee, total,
payment rule) are deterministic Python, so the answer is identical every time.

## How it is organised

- `directives/`  -  the rules in plain English. Start with `verify_order.md`.
- `execution/`   -  the Python scripts that do the work.
- `data/`        -  the editable business data: delivery fees, products, message
  templates. This is where you change fees or add products.
- `tests/`       -  proof that the logic works, using three real order cases.
- `CLAUDE.md` / `AGENTS.md` / `GEMINI.md`  -  the agent's instructions (same content,
  three names so any AI tool picks it up).

## Quick start (in Claude Code)

1. Open this folder in Claude Code. It will read `CLAUDE.md` automatically.
2. Ask it: "Verify this order" and paste an order, or just say "run the tests".
3. To run the tests yourself in a terminal:

   ```bash
   python3 tests/test_verification.py
   ```

   You should see `RESULT: 3/3 cases passed`.

4. To see a single demo order verified:

   ```bash
   python3 execution/verify_order.py
   ```

## Editing the business rules (no coding needed)

- **Change a delivery fee:** open `data/delivery_fees.json` and edit the number.
- **Add a product:** open `data/product_catalogue.json` and add a new entry with its
  name, price, and colours.
- **Change a customer message:** open `data/whatsapp_templates.json` and edit the
  wording. Keep the words in `{curly_braces}`; those get filled in automatically.

After any change, run the tests again to make sure nothing broke.

## Important note on the data

Two delivery fees are confirmed from real orders: Dubai JVC (AED 15) and Sharjah Al
Taawun (AED 20). The other emirate fees are **placeholders** and are clearly marked as
such. Confirm and edit them before relying on them. The same applies to the product
catalogue, which currently holds the two products from the test cases.

## What to build next

- Add the full product catalogue and confirmed delivery fees.
- Add an execution script to write verified orders to a Google Sheet.
- Add a script to send the drafted WhatsApp message through your provider.
- Each new task gets its own directive in `directives/` and its own script in
  `execution/`.

## Requirements

Python 3.9 or newer. The core verification uses only the Python standard library, so
there is nothing to install to run the tests. The `requirements.txt` lists packages
you will need only when you add API integrations later.
