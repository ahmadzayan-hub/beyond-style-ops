"""ops/sheets.py — Google Sheets read/write for the Beyond Style ops app."""

import os
import sys
import json
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "execution"))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_SHEET_ID = os.getenv("GOOGLE_SHEETS_ID", "")
_client   = None
_wb       = None


def _get_secret(key: str, default: str = "") -> str:
    """Read from st.secrets (Streamlit Cloud) or os.environ (local)."""
    try:
        import streamlit as st
        return st.secrets.get(key, os.getenv(key, default))
    except Exception:
        return os.getenv(key, default)


def _connect():
    global _client, _wb
    if _wb is not None:
        return _wb

    sheet_id = _get_secret("GOOGLE_SHEETS_ID") or _SHEET_ID

    # Try Streamlit Cloud path: token JSON embedded in secrets
    try:
        import streamlit as st
        token_json = st.secrets.get("GOOGLE_OAUTH_TOKEN_JSON", "")
        if token_json and token_json.strip():
            import gspread
            from google.oauth2.credentials import Credentials
            token_data = json.loads(token_json)
            creds = Credentials(
                token=token_data.get("token"),
                refresh_token=token_data.get("refresh_token"),
                token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=token_data.get("client_id"),
                client_secret=token_data.get("client_secret"),
                scopes=token_data.get("scopes", ["https://www.googleapis.com/auth/spreadsheets"]),
            )
            _client = gspread.authorize(creds)
            _wb = _client.open_by_key(sheet_id)
            return _wb
    except Exception:
        pass

    # Local path: use write_to_sheets._get_client() which handles OAuth token file
    from write_to_sheets import _get_client
    _client = _get_client()
    _wb     = _client.open_by_key(sheet_id)
    return _wb


def _ws(name: str):
    return _connect().worksheet(name)


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")


# ── Master Orders ─────────────────────────────────────────────────────────────

def get_master_orders() -> pd.DataFrame:
    ws      = _ws("Master Orders")
    records = ws.get_all_records(head=3, default_blank="")
    df      = pd.DataFrame(records)
    if df.empty:
        return df
    # Drop completely empty rows
    df = df[df["Order ID"].astype(str).str.strip() != ""]
    return df


def find_order_row(ws, order_id: str) -> int:
    """Return 1-based sheet row for this Order ID (header on row 3, data from row 4)."""
    col_vals = ws.col_values(2)  # Order ID is column B (col 2)
    for i, v in enumerate(col_vals):
        if str(v).strip() == str(order_id).strip():
            return i + 1
    return None


def _col_letter(ws, header_name: str, head_row: int = 3) -> int:
    """Return 1-based column index for a header name."""
    headers = ws.row_values(head_row)
    for i, h in enumerate(headers):
        if h.strip() == header_name.strip():
            return i + 1
    return None


def update_master_order(order_id: str, updates: dict) -> bool:
    """Update one or more columns in Master Orders for the given Order ID."""
    try:
        ws       = _ws("Master Orders")
        row      = find_order_row(ws, order_id)
        if not row:
            return False
        updates["Last Updated"] = _now()
        for col_name, value in updates.items():
            col_num = _col_letter(ws, col_name, head_row=3)
            if col_num:
                ws.update_cell(row, col_num, str(value) if value is not None else "")
        return True
    except Exception as e:
        print(f"update_master_order error: {e}")
        return False


def get_order(order_id: str) -> dict:
    """Return a single order as a dict."""
    df = get_master_orders()
    rows = df[df["Order ID"].astype(str) == str(order_id)]
    if rows.empty:
        return {}
    return rows.iloc[0].to_dict()


def get_dashboard_counts(df: pd.DataFrame = None) -> dict:
    """Return count per Order Status plus a few computed counters."""
    if df is None:
        df = get_master_orders()
    if df.empty:
        return {}

    counts = df["Order Status"].value_counts().to_dict()

    # Extra computed counters
    counts["_total"]        = len(df)
    counts["_payment_pend"] = len(df[df["Payment Status"] == "Payment Pending"])
    counts["_paid_online"]  = len(df[df["Payment Status"] == "Paid Online"])
    counts["_cod_conf"]     = len(df[df["Payment Status"] == "COD Confirmed"])
    counts["_high_risk"]    = len(df[df["Risk Status"].str.lower().isin(["high", "critical"])])
    counts["_pod_missing"]  = len(df[
        (df["Delivery Status"] == "Delivered") &
        (df["Proof of Delivery"].astype(str).str.strip() == "")
    ])
    return counts


# ── Payments ──────────────────────────────────────────────────────────────────

def get_payments() -> pd.DataFrame:
    ws      = _ws("Payments")
    records = ws.get_all_records(default_blank="")
    df      = pd.DataFrame(records)
    if df.empty:
        return df
    return df[df["Order ID"].astype(str).str.strip() != ""]


def update_payment(order_id: str, updates: dict) -> bool:
    try:
        ws      = _ws("Payments")
        headers = ws.row_values(1)
        col_map = {h.strip(): i + 1 for i, h in enumerate(headers)}
        oid_col = col_map.get("Order ID", 2)
        col_vals = ws.col_values(oid_col)
        row = None
        for i, v in enumerate(col_vals):
            if str(v).strip() == str(order_id).strip():
                row = i + 1
                break
        if not row:
            return False
        updates["Last Updated"] = _now()
        for col_name, value in updates.items():
            col_num = col_map.get(col_name)
            if col_num:
                ws.update_cell(row, col_num, str(value) if value is not None else "")
        return True
    except Exception as e:
        print(f"update_payment error: {e}")
        return False


# ── Packing QC ────────────────────────────────────────────────────────────────

def get_packing_qc() -> pd.DataFrame:
    try:
        ws      = _ws("Packing QC")
        records = ws.get_all_records(default_blank="")
        df      = pd.DataFrame(records)
        if df.empty:
            return df
        # find Order ID column
        oid_col = next((c for c in df.columns if "order" in c.lower() and "id" in c.lower()), None)
        if oid_col:
            df = df[df[oid_col].astype(str).str.strip() != ""]
        return df
    except Exception:
        return pd.DataFrame()


def update_packing_qc(order_id: str, updates: dict) -> bool:
    try:
        ws      = _ws("Packing QC")
        headers = ws.row_values(1)
        col_map = {h.strip(): i + 1 for i, h in enumerate(headers)}
        oid_col_num = None
        for h, n in col_map.items():
            if "order" in h.lower() and "id" in h.lower():
                oid_col_num = n
                break
        if not oid_col_num:
            return False
        col_vals = ws.col_values(oid_col_num)
        row = None
        for i, v in enumerate(col_vals):
            if str(v).strip() == str(order_id).strip():
                row = i + 1
                break
        if not row:
            return False
        for col_name, value in updates.items():
            col_num = col_map.get(col_name)
            if col_num:
                ws.update_cell(row, col_num, str(value) if value is not None else "")
        return True
    except Exception as e:
        print(f"update_packing_qc error: {e}")
        return False


# ── Courier Tracking ──────────────────────────────────────────────────────────

def get_courier_tracking() -> pd.DataFrame:
    try:
        ws      = _ws("Courier Tracking")
        records = ws.get_all_records(default_blank="")
        df      = pd.DataFrame(records)
        if df.empty:
            return df
        return df[df["Order ID"].astype(str).str.strip() != ""]
    except Exception:
        return pd.DataFrame()


def update_courier(order_id: str, updates: dict) -> bool:
    try:
        ws      = _ws("Courier Tracking")
        headers = ws.row_values(1)
        col_map = {h.strip(): i + 1 for i, h in enumerate(headers)}
        col_vals = ws.col_values(col_map.get("Order ID", 2))
        row = None
        for i, v in enumerate(col_vals):
            if str(v).strip() == str(order_id).strip():
                row = i + 1
                break
        if not row:
            return False
        for col_name, value in updates.items():
            col_num = col_map.get(col_name)
            if col_num:
                ws.update_cell(row, col_num, str(value) if value is not None else "")
        return True
    except Exception as e:
        print(f"update_courier error: {e}")
        return False


# ── Product Catalog ───────────────────────────────────────────────────────────

def get_product_catalog() -> pd.DataFrame:
    try:
        ws      = _ws("Product Catalog")
        records = ws.get_all_records(default_blank="")
        df      = pd.DataFrame(records)
        return df[df["Product Name EN"].astype(str).str.strip() != ""] if not df.empty else df
    except Exception:
        return pd.DataFrame()


# ── Customer DB ───────────────────────────────────────────────────────────────

def get_customer_db() -> pd.DataFrame:
    try:
        ws      = _ws("Customer DB")
        records = ws.get_all_records(default_blank="")
        df      = pd.DataFrame(records)
        return df[df["Customer Name"].astype(str).str.strip() != ""] if not df.empty else df
    except Exception:
        return pd.DataFrame()
