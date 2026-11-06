# Dashboard order integrity

## Shared save boundary

All dashboard write helpers now check authorization, read the current worksheet
rows, check required columns and a unique Order ID, and validate the merged record
before saving anything. Missing or duplicate columns/IDs fail closed rather than
silently omitting a requested field or updating the first ambiguous match.

Delivered and POD Received require Receiver Name, Staff Number (N/A is permitted),
Actual Received Date, and Proof of Delivery. This applies to Order Status,
Delivery Status, and Courier Status, including the POD shortcut. The shortcut
saves evidence entered in the form together with the status. Evidence cannot be
cleared while a record still claims delivery or successful closeout.

Successful closeout additionally requires Delivery Status to be Delivered or POD
Received and a Customer Satisfaction Score. The Orders shortcut and Reviews page
now enforce the same requirements. Label readiness rechecks approved/passed QC
from the current worksheet, not only the cached page.

This change does not define a new complete lifecycle transition graph or verify
that a receipt/URL is authentic. Existing business policies and authorization
boundaries remain in effect.

## One atomic workbook write

All requested cells are sent together using one Google Sheets
[`spreadsheets.batchUpdate`](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/batchUpdate)
request. Google validates the batch and applies its requests atomically. Only
`userEnteredValue` is changed, with explicit string values so supplied text is not
interpreted as a formula. Unrelated cells, formulas, and formatting are preserved.

The payment form saves Payments and Master Orders in that same workbook batch.
Both records must exist, even when the page displays a fallback from Master
Orders. Missing payment records now block the save instead of dropping payment
references/notes or reporting a partial update as successful. No records or
columns are automatically created or renamed. Master Orders and Payments must
include a unique Last Updated column.

A lost response after submission may mean the whole batch already succeeded.
The UI therefore clears cached reads, reports "Update not confirmed", and
instructs the operator to refresh and verify before retrying. It does not retry automatically, claim no
changes were written, print provider payloads, or report success.

## Remaining acceptance limits

- Fresh reads and atomic writes are not a transaction across the read/write gap.
  Google Sheets does not give these calls an order-level compare-and-swap guard.
  Another writer or a row insertion/reorder after validation can still race the
  request. Avoid simultaneous writers/structural edits during order updates;
  strong concurrent workflow guarantees require a transactional backing store.
- This is dashboard scope. The standalone verification/import scripts are not
  migrated by this change. Their separate acceptance requirements still apply.
- Only local synthetic regression tests were used for the changed dashboard.
  No live account, operational order, Google Sheets write, or deployment was used.
- Before real-data rollout, confirm worksheet schemas and rows in an approved
  non-production workbook and complete the authentication rollout checklist in
  OPS_AUTH_SETUP.md. Synthetic mocks test request construction and failure paths,
  not live provider acceptance.

## Tests

```
python -m unittest discover -s tests -p "test_auth*.py" -v
python -m unittest discover -s tests -p "test_integrity*.py" -v
```

The integrity tests cover required evidence, clearing evidence, fresh reads,
shortcut/form parity, missing/duplicate schema and IDs, authorization rechecks,
late batch rejection, cross-sheet payment failures, literal writes, lost responses,
and the absence of per-cell write calls. All data and identity claims are synthetic.
