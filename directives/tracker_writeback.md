# Directive: Tracker Write-Back (Google Sheets)

Layer 1 (Directive). Rules for writing order verification results back to the
existing Beyond Style Google Sheets tracker.

## Goal

Keep the Master Orders sheet accurate and up-to-date after every verification
run, without overwriting owner notes or disrupting existing data.

## Sheet details

- Workbook: existing Beyond Style UAE Google Sheet
- Main sheet: **Master Orders**
- Header row: **3**
- Raw intake: Form Responses
- Message templates: Customer Messages

## Column mapping

Defined in `config/google_sheet_column_map.json`.
Edit that file if column headers in the sheet ever change.
Never rename or delete existing columns without owner approval.

## Write-back rules

1. Always read the existing row first; only update relevant fields.
2. Preserve the `Internal Notes` column — never overwrite it.
3. Write these fields after every verification run:
   - Verification Status
   - Risk Level
   - Escalation Required
   - Escalation Reason
   - WhatsApp Number (normalised E.164)
   - WhatsApp Message Sent / Type / Time / Meta Message ID
   - Last Updated
4. Only write Verified orders to a dispatch queue.

## Execution scripts

| Script | Role |
|---|---|
| `execution/build_tracker_update.py` | Builds the column→value mapping dict from a result |
| `execution/write_to_sheets.py` | Opens the sheet via gspread and writes/appends the row |

`write_to_sheets.py` exposes two functions:
- `write_order_result(order, result, send_result, order_id)` — upsert a row
- `test_connection()` — smoke test; run directly: `python execution/write_to_sheets.py`

A keyed order keeps its Order ID on every append. Existing orders are updated in one batch.
Customer values are written as raw values, including text that starts with a formula character.
Internal Notes remain outside the batch.

Use the same local write-state database for every verifier sharing a workbook on a host.
It defaults to `.runtime/sheet-writes.sqlite3` and can be set with `GOOGLE_SHEETS_WRITE_STATE`.
An uncertain append is reconciled by checking the live row for its Order ID on the next attempt.
If the row is still absent, the writer keeps the reservation for operator reconciliation.
Separate hosts require a shared authoritative order store before running concurrent writers.

## Status

- gspread 6.2.1 installed (2026-06-09)
- GOOGLE_SHEETS_ID set in .env
- GOOGLE_SERVICE_ACCOUNT_JSON still needs service account key — see below

## Service account setup (one-time)

1. Go to https://console.cloud.google.com → select or create a project
2. APIs & Services → Enable API → search "Google Sheets API" → Enable
3. Also enable "Google Drive API"
4. APIs & Services → Credentials → Create Credentials → Service Account
5. Name: `beyond-style-sheets` → Create → Done
6. Click the new service account → Keys tab → Add Key → JSON → download file
7. Save the JSON file somewhere safe (e.g. `C:\Users\ahmad\.config\beyond-style-sa.json`)
8. In `.env`, set: `GOOGLE_SERVICE_ACCOUNT_JSON=C:\Users\ahmad\.config\beyond-style-sa.json`
9. Open the Google Sheet → Share → paste the service account email (ends in `@...gserviceaccount.com`) → Editor
10. Test: `python execution/write_to_sheets.py`
