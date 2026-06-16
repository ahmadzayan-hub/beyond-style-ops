# Directive: Product Catalogue Check

Layer 1 (Directive). Rules for validating product name, colour, and price.

## Goal

Ensure the customer is ordering a real product at the correct price in an
available colour, and that no unsupported claims are made about the product.

## Source of truth

`data/product_catalogue.json` — edit this file to add products, correct prices,
or add confirmed colours.

## Validation rules

1. Product name must match a catalogue entry (case-insensitive).
   Unknown product → **Needs Correction**.
2. If the catalogue entry has a non-empty `colours` list, the order colour must
   match one of those colours (case-insensitive).
   Mismatch → **Needs Correction**.
3. Unit price in the order must match the catalogue `unit_price`.
   Mismatch → **Needs Correction**, use catalogue price for recalculation.
4. Products with `"colours": []` have colour TBC from real photo — skip colour check.
5. Products with `"status": "imported"` need real photo confirmation before making
   any colour or material claims to the customer.

## Approved product descriptions

- Fashion Jewellery
- Fashion Accessories

## Approved material claims (only if supplier confirmed in writing)

- 316L Surgical Stainless Steel (PVD Vacuum Plated)
- Solid 925 Sterling Silver

**Never claim:** real gold, real silver, waterproof, anti-tarnish, or fixed colour
unless the supplier has confirmed it in writing.

## Care instructions (when customer asks)

"Please keep it away from direct water, concentrated perfume, alcohol sanitisers,
and high friction."

## Adding new products

Edit `data/product_catalogue.json`. Add `sku`, `name`, `category`, `unit_price`,
`colours` (empty list if TBC), and `status`. Run the test suite after every change.
