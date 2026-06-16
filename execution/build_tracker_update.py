"""
build_tracker_update.py  -  Layer 3 (Execution)

Builds the Google Sheets row-update dict, mapping order + verification result
fields to Master Orders column names from config/google_sheet_column_map.json.

This script only builds the mapping dict. Writing to Sheets requires gspread
and credentials — that is done in a separate integration script.
"""

import json
import os
from datetime import datetime

_MAP_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "config", "google_sheet_column_map.json"
)


def _load_map():
    with open(_MAP_FILE, encoding="utf-8") as f:
        return json.load(f)


def build_tracker_update(order: dict, result: dict, send_result: dict = None) -> dict:
    """
    Args:
        order:       13-field order dict
        result:      8-section verification result from validate_order
        send_result: optional dict from send_whatsapp_message

    Returns:
        ok:      bool
        mapping: dict  - {sheet_column_name: value}
        reason:  str
    """
    try:
        col = _load_map()
    except Exception as e:
        return {"ok": False, "mapping": {}, "reason": f"Could not load column map: {e}"}

    now        = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    phone_info = result.get("phone_normalized", {})

    mapping = {
        col["customer_name"]:       order.get("customer_name", ""),
        col["original_phone"]:      order.get("phone", ""),
        col["normalized_phone"]:    phone_info.get("international", ""),
        col["emirate"]:             order.get("emirate", ""),
        col["area"]:                order.get("area", ""),
        col["full_address"]:        order.get("address", ""),
        col["google_maps_link"]:    order.get("maps_link", ""),
        col["product_name"]:        order.get("product", ""),
        col["colour"]:              order.get("colour", ""),
        col["quantity"]:            order.get("quantity", ""),
        col["unit_price"]:          order.get("unit_price", ""),
        col["delivery_fee"]:        order.get("delivery_fee", ""),
        col["discount"]:            order.get("discount", ""),
        col["total_amount"]:        order.get("total", ""),
        col["payment_method"]:      order.get("payment_method", ""),
        col["payment_status"]:      order.get("payment_status", ""),
        col["verification_status"]: result.get("operational_status", ""),
        col["risk_level"]:          result.get("risk_level", ""),
        col["escalation_required"]: "YES" if result.get("escalation") else "No",
        col["escalation_reason"]:   "; ".join(result.get("missing_or_risky", [])),
        col["last_updated"]:        now,
    }

    if send_result:
        mapping[col["whatsapp_message_sent"]] = "Yes" if send_result.get("sent") else "No"
        mapping[col["whatsapp_message_type"]] = result.get("message_type", "")
        mapping[col["whatsapp_sent_time"]]    = send_result.get("timestamp", "")
        mapping[col["meta_message_id"]]       = send_result.get("message_id", "")

    return {"ok": True, "mapping": mapping, "reason": ""}
