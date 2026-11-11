"""ops/sheets.py — Google Sheets read/write for the Beyond Style ops app."""

import os
import sys
from dataclasses import dataclass
import pandas as pd
from datetime import datetime, timezone
from ops.auth import assert_access, assert_update
from ops.integrity import UpdateValidationError, validate_order_update

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
    assert_access()
    global _client, _wb
    if _wb is not None:
        return _wb

    sheet_id = _get_secret("GOOGLE_SHEETS_ID") or _SHEET_ID

    # Try Streamlit Cloud path: individual fields stored under [google_oauth] section
    try:
        import streamlit as st
        import gspread
        from google.oauth2.credentials import Credentials

        oauth = st.secrets.get("google_oauth", {})
        if oauth and oauth.get("refresh_token"):
            scopes = oauth.get("scopes", ["https://www.googleapis.com/auth/spreadsheets"])
            if isinstance(scopes, str):
                scopes = [s.strip() for s in scopes.split(",")]
            creds = Credentials(
                token=oauth.get("token", ""),
                refresh_token=oauth["refresh_token"],
                token_uri=oauth.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=oauth["client_id"],
                client_secret=oauth["client_secret"],
                scopes=scopes,
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
    assert_access()
    return _connect().worksheet(name)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _ws_to_df(ws, head_row: int = 1) -> pd.DataFrame:
    """Read a worksheet into a DataFrame without crashing on duplicate/empty headers.

    Uses get_all_values() instead of get_all_records() so blank or duplicate
    header columns are handled safely by deduplicating them with a numeric suffix.
    """
    all_vals = ws.get_all_values()
    if not all_vals or len(all_vals) < head_row:
        return pd.DataFrame()

    raw_headers = all_vals[head_row - 1]
    data_rows   = all_vals[head_row:]

    # Deduplicate headers: blank cols become _col_N, dupes get _2, _3 ...
    seen: dict = {}
    headers = []
    for i, h in enumerate(raw_headers):
        h = h.strip()
        if not h:
            h = f"_col_{i + 1}"
        if h in seen:
            seen[h] += 1
            h = f"{h}_{seen[h]}"
        else:
            seen[h] = 1
        headers.append(h)

    if not data_rows:
        return pd.DataFrame(columns=headers)

    # Pad or trim each row to match header count
    n = len(headers)
    padded = [row[:n] + [""] * max(0, n - len(row)) for row in data_rows]

    df = pd.DataFrame(padded, columns=headers)
    # Drop rows that are entirely empty
    df = df[df.apply(lambda r: any(str(v).strip() for v in r), axis=1)].reset_index(drop=True)
    return df


# ── Master Orders ─────────────────────────────────────────────────────────────

def get_master_orders() -> pd.DataFrame:
    ws = _ws("Master Orders")
    df = _ws_to_df(ws, head_row=3)
    if df.empty:
        return df
    if "Order ID" in df.columns:
        df = df[df["Order ID"].astype(str).str.strip() != ""]
    return df


@dataclass(frozen=True)
class UpdateResult:
    success: bool
    message: str = ""
    uncertain: bool = False

    def __bool__(self):
        return self.success


def _prepare_update(ws, resource, order_id, updates):
    """Read fresh data and validate every target before constructing any write."""
    head_row = 3 if resource == "Master Orders" else 1
    rows = ws.get_all_values()
    if len(rows) < head_row:
        raise UpdateValidationError("Worksheet headers are missing. Ask the owner to check the sheet.")
    headers = [str(h).strip() for h in rows[head_row - 1]]
    changes = dict(updates)
    if resource in {"Master Orders", "Payments"}:
        changes["Last Updated"] = _now()
    required = {"Order ID", *changes}
    if any(headers.count(field) != 1 for field in required):
        raise UpdateValidationError("A required worksheet column is missing or duplicated. No changes were saved.")
    # Reject duplicate nonempty headers rather than interpreting an ambiguous record.
    nonempty = [h for h in headers if h]
    if len(nonempty) != len(set(nonempty)):
        raise UpdateValidationError("Worksheet columns are duplicated. No changes were saved.")
    oid = str(order_id).strip() if order_id is not None else ""
    if not oid:
        raise UpdateValidationError("Choose a nonempty Order ID.")
    oid_col = headers.index("Order ID")
    matches = [(i, row) for i, row in enumerate(rows[head_row:], start=head_row)
               if len(row) > oid_col and str(row[oid_col]).strip() == oid]
    if len(matches) != 1:
        raise UpdateValidationError("The order is missing or duplicated in a required worksheet. No changes were saved.")
    row_index, values = matches[0]
    current = {header: values[i] if i < len(values) else ""
               for i, header in enumerate(headers) if header}
    if resource in {"Master Orders", "Courier Tracking"}:
        validate_order_update(current, changes)
    requests = []
    for field, value in changes.items():
        requests.append({"updateCells": {
            "start": {"sheetId": ws.id, "rowIndex": row_index, "columnIndex": headers.index(field)},
            "rows": [{"values": [{"userEnteredValue": {"stringValue": "" if value is None else str(value)}}]}],
            "fields": "userEnteredValue",
        }})
    return requests


def update_order_records(order_id: str, changes_by_resource: dict) -> UpdateResult:
    """Validate all records, then commit all cells in one atomic Sheets request.

    Authorization errors propagate. A transport failure after submission is
    uncertain: do not retry automatically or claim that nothing was written.
    """
    for resource, updates in changes_by_resource.items():
        assert_update(resource, updates)
    if not changes_by_resource:
        raise PermissionError("This account cannot make an empty update.")
    try:
        workbook = _connect()
        requests = []
        for resource, updates in changes_by_resource.items():
            ws = workbook.worksheet(resource)
            requests.extend(_prepare_update(ws, resource, order_id, updates))
        # Recheck roles after the reads, just before committing the complete batch.
        for resource, updates in changes_by_resource.items():
            assert_update(resource, updates)
    except PermissionError:
        raise
    except UpdateValidationError as error:
        return UpdateResult(False, str(error))
    except Exception:
        return UpdateResult(False, "The worksheets could not be checked. No changes were submitted.")
    try:
        # spreadsheets.batchUpdate is atomic across all requests in this workbook.
        # Explicit stringValue avoids interpreting user text as a formula.
        workbook.batch_update({"requests": requests})
        return UpdateResult(True)
    except Exception:
        return UpdateResult(False, "Update not confirmed. Refresh and verify the saved values before retrying.",
                            uncertain=True)


def update_master_order(order_id: str, updates: dict) -> UpdateResult:
    return update_order_records(order_id, {"Master Orders": updates})


def update_payment_and_master(order_id: str, payment_updates: dict, master_updates: dict) -> UpdateResult:
    return update_order_records(order_id, {"Payments": payment_updates, "Master Orders": master_updates})


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

    counts = df["Order Status"].value_counts().to_dict() if "Order Status" in df.columns else {}

    counts["_total"]        = len(df)
    counts["_payment_pend"] = len(df[df["Payment Status"] == "Payment Pending"]) if "Payment Status" in df.columns else 0
    counts["_paid_online"]  = len(df[df["Payment Status"] == "Paid Online"])     if "Payment Status" in df.columns else 0
    counts["_cod_conf"]     = len(df[df["Payment Status"] == "COD Confirmed"])   if "Payment Status" in df.columns else 0
    counts["_high_risk"]    = (
        len(df[df["Risk Status"].str.lower().isin(["high", "critical"])])
        if "Risk Status" in df.columns else 0
    )
    counts["_pod_missing"]  = (
        len(df[
            (df["Delivery Status"] == "Delivered") &
            (df["Proof of Delivery"].astype(str).str.strip() == "")
        ])
        if "Delivery Status" in df.columns and "Proof of Delivery" in df.columns else 0
    )
    return counts


# ── Payments ──────────────────────────────────────────────────────────────────

def get_payments() -> pd.DataFrame:
    ws = _ws("Payments")
    df = _ws_to_df(ws)
    if df.empty:
        return df
    if "Order ID" in df.columns:
        df = df[df["Order ID"].astype(str).str.strip() != ""]
    return df


def update_payment(order_id: str, updates: dict) -> UpdateResult:
    return update_order_records(order_id, {"Payments": updates})


# ── Packing QC ────────────────────────────────────────────────────────────────

def get_packing_qc() -> pd.DataFrame:
    try:
        ws = _ws("Packing QC")
        df = _ws_to_df(ws)
        if df.empty:
            return df
        oid_col = next((c for c in df.columns if "order" in c.lower() and "id" in c.lower()), None)
        if oid_col:
            df = df[df[oid_col].astype(str).str.strip() != ""]
        return df
    except Exception:
        return pd.DataFrame()


def update_packing_qc(order_id: str, updates: dict) -> UpdateResult:
    return update_order_records(order_id, {"Packing QC": updates})


# ── Courier Tracking ──────────────────────────────────────────────────────────

def get_courier_tracking() -> pd.DataFrame:
    try:
        ws = _ws("Courier Tracking")
        df = _ws_to_df(ws)
        if df.empty:
            return df
        if "Order ID" in df.columns:
            df = df[df["Order ID"].astype(str).str.strip() != ""]
        return df
    except Exception:
        return pd.DataFrame()


def update_courier(order_id: str, updates: dict) -> UpdateResult:
    return update_order_records(order_id, {"Courier Tracking": updates})


# ── Product Catalog ───────────────────────────────────────────────────────────

def get_product_catalog() -> pd.DataFrame:
    try:
        ws = _ws("Product Catalog")
        df = _ws_to_df(ws)
        if df.empty:
            return df
        col = next((c for c in df.columns if "product name" in c.lower() and "en" in c.lower()), None)
        if col:
            df = df[df[col].astype(str).str.strip() != ""]
        return df
    except Exception:
        return pd.DataFrame()


# ── Customer DB ───────────────────────────────────────────────────────────────

def get_customer_db() -> pd.DataFrame:
    try:
        ws = _ws("Customer DB")
        df = _ws_to_df(ws)
        if df.empty:
            return df
        col = next((c for c in df.columns if "customer" in c.lower() and "name" in c.lower()), None)
        if col:
            df = df[df[col].astype(str).str.strip() != ""]
        return df
    except Exception:
        return pd.DataFrame()
