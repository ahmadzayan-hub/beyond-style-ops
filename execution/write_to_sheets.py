"""
write_to_sheets.py  -  Layer 3 (Execution)

Writes a verified order's result back to the Beyond Style UAE Master Orders
Google Sheet. Supports two auth methods (auto-detected):

  1. OAuth 2.0 (default / recommended)
     - Set GOOGLE_OAUTH_CREDENTIALS in .env to the path of credentials.json
       downloaded from Google Cloud Console (OAuth 2.0 Client ID, Desktop app).
     - On first run a browser opens for one-time sign-in; token saved to
       GOOGLE_OAUTH_TOKEN path (default: config/google_token.json).
     - No service account key needed — works even when org policy blocks key creation.

  2. Service Account JSON (fallback)
     - Set GOOGLE_SERVICE_ACCOUNT_JSON in .env to the path of the key file.
     - Used automatically if GOOGLE_OAUTH_CREDENTIALS is not set.

Requires:
    pip install gspread google-auth-oauthlib python-dotenv

Run connection test:
    python execution/write_to_sheets.py
"""

import os
import json
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

GOOGLE_SHEETS_ID            = os.getenv("GOOGLE_SHEETS_ID", "")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
GOOGLE_OAUTH_CREDENTIALS    = os.getenv("GOOGLE_OAUTH_CREDENTIALS", "")
# Where to cache the OAuth access token after first login
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOOGLE_OAUTH_TOKEN = os.getenv(
    "GOOGLE_OAUTH_TOKEN",
    os.path.join(_ROOT, "config", "google_token.json"),
)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Sheet config (matches config/google_sheet_column_map.json)
SHEET_NAME = "Master Orders"
HEADER_ROW = 3          # row index where column headers live (1-based)
DATA_START  = 4         # first data row (1-based), right after header

_col_map = None


def _load_col_map():
    global _col_map
    if _col_map is None:
        map_path = os.path.join(_ROOT, "config", "google_sheet_column_map.json")
        with open(map_path, encoding="utf-8") as f:
            _col_map = json.load(f)
    return _col_map


def _get_client():
    """
    Return an authorised gspread client.

    Auth priority:
      1. OAuth 2.0  (GOOGLE_OAUTH_CREDENTIALS is set)
      2. Service account JSON  (GOOGLE_SERVICE_ACCOUNT_JSON is set)
    """
    try:
        import gspread
    except ImportError:
        raise RuntimeError(
            "gspread is not installed. Run: pip install gspread google-auth-oauthlib"
        )

    # ── OAuth 2.0 path ────────────────────────────────────────────────────────
    if GOOGLE_OAUTH_CREDENTIALS:
        creds_path = GOOGLE_OAUTH_CREDENTIALS.strip()
        if not os.path.isfile(creds_path):
            raise RuntimeError(
                f"GOOGLE_OAUTH_CREDENTIALS file not found: {creds_path}"
            )
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
        except ImportError:
            raise RuntimeError(
                "google-auth-oauthlib is not installed. "
                "Run: pip install google-auth-oauthlib"
            )

        creds = None
        # Load cached token if available
        if os.path.isfile(GOOGLE_OAUTH_TOKEN):
            creds = Credentials.from_authorized_user_file(GOOGLE_OAUTH_TOKEN, SCOPES)

        # Refresh or run browser login if needed
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                creds = flow.run_local_server(port=0)
            # Save token for next run
            os.makedirs(os.path.dirname(GOOGLE_OAUTH_TOKEN), exist_ok=True)
            with open(GOOGLE_OAUTH_TOKEN, "w") as f:
                f.write(creds.to_json())

        return gspread.authorize(creds)

    # ── Service account JSON path ─────────────────────────────────────────────
    if GOOGLE_SERVICE_ACCOUNT_JSON:
        try:
            from google.oauth2.service_account import Credentials
        except ImportError:
            raise RuntimeError(
                "google-auth is not installed. Run: pip install google-auth"
            )
        key_path = GOOGLE_SERVICE_ACCOUNT_JSON.strip()
        if os.path.isfile(key_path):
            creds = Credentials.from_service_account_file(key_path, scopes=SCOPES)
        else:
            try:
                info  = json.loads(key_path)
                creds = Credentials.from_service_account_info(info, scopes=SCOPES)
            except json.JSONDecodeError:
                raise RuntimeError(
                    f"GOOGLE_SERVICE_ACCOUNT_JSON is not a valid file path or JSON."
                )
        return gspread.authorize(creds)

    raise RuntimeError(
        "No Google credentials configured. Set GOOGLE_OAUTH_CREDENTIALS "
        "(recommended) or GOOGLE_SERVICE_ACCOUNT_JSON in .env"
    )


def _open_sheet():
    """Open the Master Orders worksheet."""
    if not GOOGLE_SHEETS_ID:
        raise RuntimeError("GOOGLE_SHEETS_ID is not set in .env.")

    client = _get_client()
    spreadsheet = client.open_by_key(GOOGLE_SHEETS_ID)
    return spreadsheet.worksheet(SHEET_NAME)


def _build_col_index(ws) -> dict:
    """
    Read the header row from the sheet and return a dict:
    { column_header_string: column_index_int (1-based) }
    """
    header = ws.row_values(HEADER_ROW)
    return {name.strip(): idx + 1 for idx, name in enumerate(header) if name.strip()}


def _find_order_row(ws, col_index: dict, order_id: str) -> int:
    """
    Find the row number of an existing order by Order ID.
    Returns None if not found.
    """
    order_id_col = col_index.get("Order ID")
    if not order_id_col or not order_id:
        return None

    col_letter = _col_num_to_letter(order_id_col)
    cell_list = ws.findall(str(order_id), in_column=order_id_col)
    for cell in cell_list:
        if cell.row >= DATA_START:
            return cell.row
    return None


def _col_num_to_letter(n: int) -> str:
    """Convert 1-based column number to letter(s), e.g. 1→A, 27→AA."""
    result = ""
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result
    return result


def write_order_result(
    order: dict,
    result: dict,
    send_result: dict = None,
    order_id: str = None,
) -> dict:
    """
    Write or update an order row in Master Orders.

    - If order_id matches an existing row → update that row in place.
    - Otherwise → append a new row after the last data row.

    Args:
        order:       13-field order dict
        result:      8-section verification result from validate_order
        send_result: optional dict from send_whatsapp_message
        order_id:    optional Order ID to match an existing row

    Returns:
        ok:      bool
        row:     int   - sheet row number written
        action:  str   - "updated" | "appended"
        reason:  str
    """
    try:
        ws        = _open_sheet()
        col_index = _build_col_index(ws)
        col_map   = _load_col_map()
    except Exception as e:
        return {"ok": False, "row": None, "action": "", "reason": str(e)}

    now          = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    phone_info   = result.get("phone_normalized", {})

    # Build the field→value mapping using the column map
    field_values = {
        col_map["customer_name"]:       order.get("customer_name", ""),
        col_map["original_phone"]:      order.get("phone", ""),
        col_map["normalized_phone"]:    phone_info.get("international", ""),
        col_map["emirate"]:             order.get("emirate", ""),
        col_map["area"]:                order.get("area", ""),
        col_map["full_address"]:        order.get("address", ""),
        col_map["google_maps_link"]:    order.get("maps_link", ""),
        col_map["product_name"]:        order.get("product", ""),
        col_map["colour"]:              order.get("colour", ""),
        col_map["quantity"]:            order.get("quantity", ""),
        col_map["unit_price"]:          order.get("unit_price", ""),
        col_map["delivery_fee"]:        order.get("delivery_fee", ""),
        col_map["discount"]:            order.get("discount", ""),
        col_map["total_amount"]:        order.get("total", ""),
        col_map["payment_method"]:      order.get("payment_method", ""),
        col_map["payment_status"]:      order.get("payment_status", ""),
        col_map["verification_status"]: result.get("operational_status", ""),
        col_map["risk_level"]:          result.get("risk_level", ""),
        col_map["escalation_required"]: "YES" if result.get("escalation") else "No",
        col_map["escalation_reason"]:   "; ".join(result.get("missing_or_risky", [])),
        col_map["last_updated"]:        now,
    }

    if send_result:
        field_values[col_map["whatsapp_message_sent"]] = (
            "Yes" if send_result.get("sent") else "No"
        )
        field_values[col_map["whatsapp_message_type"]] = result.get("message_type", "")
        field_values[col_map["whatsapp_sent_time"]]    = send_result.get("timestamp", "")
        field_values[col_map["meta_message_id"]]       = send_result.get("message_id", "")

    # Try to update existing row
    target_row = _find_order_row(ws, col_index, order_id) if order_id else None

    if target_row:
        # update only the cells we manage — never touch Internal Notes
        protected = {col_map.get("owner_notes")}
        for col_name, value in field_values.items():
            if col_name in protected:
                continue
            col_num = col_index.get(col_name)
            if col_num:
                ws.update_cell(target_row, col_num, str(value) if value != "" else "")
        return {"ok": True, "row": target_row, "action": "updated", "reason": ""}

    # Append new row
    # Build a full-width row list in column order
    max_col = max(col_index.values()) if col_index else 0
    new_row  = [""] * max_col
    for col_name, value in field_values.items():
        col_num = col_index.get(col_name)
        if col_num and col_num <= max_col:
            new_row[col_num - 1] = str(value) if value != "" else ""

    ws.append_row(new_row, value_input_option="USER_ENTERED")
    all_values   = ws.get_all_values()
    appended_row = len(all_values)    # last row written
    return {"ok": True, "row": appended_row, "action": "appended", "reason": ""}


def test_connection() -> dict:
    """
    Smoke test: open the sheet and read the header row.
    Returns the column headers found and the sheet title.
    """
    try:
        ws      = _open_sheet()
        headers = [h for h in ws.row_values(HEADER_ROW) if h.strip()]
        return {
            "ok":      True,
            "title":   ws.title,
            "columns": headers,
            "count":   len(headers),
            "reason":  "",
        }
    except Exception as e:
        return {"ok": False, "title": "", "columns": [], "count": 0, "reason": str(e)}


if __name__ == "__main__":
    print("Testing Google Sheets connection...")
    r = test_connection()
    if r["ok"]:
        print(f"Connected to sheet: '{r['title']}'")
        print(f"Found {r['count']} columns:")
        for col in r["columns"]:
            print(f"  - {col}")
    else:
        print(f"Connection failed: {r['reason']}")
