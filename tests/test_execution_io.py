"""
test_execution_io.py  -  Layer 3 execution-IO coverage for write_to_sheets.py and
send_whatsapp_message.py.

test_directives.py explicitly defers these two: "the gspread writer needs
credentials and is not run here" and the WhatsApp message generator is "covered
for text generation only (nothing is sent)". This file closes that gap with a
fake gspread worksheet and a fake HTTP transport, so neither script's real logic
(column mapping, update-vs-append row matching, owner-notes protection, dry-run
vs live WhatsApp send) ever runs against a real network call or credential.

Run:  python -m unittest tests.test_execution_io -v
"""
import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "execution"))

import write_to_sheets as wts
import send_whatsapp_message as swm

ROOT = Path(__file__).resolve().parent.parent
with open(ROOT / "config" / "google_sheet_column_map.json", encoding="utf-8") as f:
    _RAW_MAP = json.load(f)
COL_MAP = {k: v for k, v in _RAW_MAP.items() if not k.startswith("_") and k not in ("sheet_name", "header_row")}
HEADER = list(COL_MAP.values())


class FakeWorksheet:
    """Minimal gspread worksheet stand-in. Never performs network I/O."""

    def __init__(self, data_rows=None):
        self.title = wts.SHEET_NAME
        self._rows = {wts.HEADER_ROW: list(HEADER)}
        for offset, row in enumerate(data_rows or []):
            self._rows[wts.DATA_START + offset] = list(row)
        self.updates = []
        self.appended = []

    def row_values(self, row):
        return list(self._rows.get(row, []))

    def findall(self, value, in_column):
        idx = in_column - 1
        hits = []
        for row_num, row in self._rows.items():
            if row_num < wts.DATA_START:
                continue
            if idx < len(row) and row[idx] == value:
                hits.append(MagicMock(row=row_num))
        return hits

    def update_cell(self, row, col, value):
        self.updates.append((row, col, value))
        r = self._rows.setdefault(row, [])
        while len(r) < col:
            r.append("")
        r[col - 1] = value

    def append_row(self, row, value_input_option=None):
        self.appended.append(list(row))
        new_row_num = (max(self._rows) if self._rows else 0) + 1
        self._rows[new_row_num] = list(row)

    def get_all_values(self):
        max_row = max(self._rows) if self._rows else 0
        return [self._rows.get(i, []) for i in range(1, max_row + 1)]


ORDER = {
    "customer_name": "Fatima Al Marri", "phone": "0501234567",
    "emirate": "Dubai", "area": "JVC",
    "address": "Villa 45, Al Manara Street, near Emirates Mall",
    "maps_link": "https://maps.app.goo.gl/x",
    "product": "Gold Layered Chain Necklace", "colour": "Gold", "quantity": 1,
    "unit_price": 89, "delivery_fee": 25, "total": 114,
    "payment_method": "Cash on Delivery", "payment_status": "Pending",
}
RESULT = {
    "phone_normalized": {"international": "971501234567"},
    "operational_status": "Awaiting Confirmation",
    "risk_level": "Low",
    "escalation": False,
    "missing_or_risky": [],
}


class ColNumToLetterTests(unittest.TestCase):
    def test_single_letters(self):
        self.assertEqual(wts._col_num_to_letter(1), "A")
        self.assertEqual(wts._col_num_to_letter(26), "Z")

    def test_double_letters(self):
        self.assertEqual(wts._col_num_to_letter(27), "AA")
        self.assertEqual(wts._col_num_to_letter(52), "AZ")


class BuildColIndexTests(unittest.TestCase):
    def test_maps_every_header_to_its_one_based_column(self):
        ws = FakeWorksheet()
        idx = wts._build_col_index(ws)
        self.assertEqual(idx["Customer Name"], HEADER.index("Customer Name") + 1)
        self.assertEqual(idx["Order ID"], 1)


class WriteOrderResultTests(unittest.TestCase):
    def setUp(self):
        self.ws = FakeWorksheet()
        self.patcher = patch.object(wts, "_open_sheet", return_value=self.ws)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_appends_a_new_row_with_the_full_field_mapping(self):
        out = wts.write_order_result(ORDER, RESULT)
        self.assertTrue(out["ok"])
        self.assertEqual(out["action"], "appended")
        row = self.ws.appended[0]
        col = wts._build_col_index(self.ws)
        self.assertEqual(row[col["Customer Name"] - 1], "Fatima Al Marri")
        self.assertEqual(row[col["WhatsApp Number"] - 1], "971501234567")
        self.assertEqual(row[col["Critical Data Status"] - 1], "Awaiting Confirmation")
        self.assertEqual(row[col["Escalation Required"] - 1], "No")

    def test_escalation_required_yes_with_joined_reasons(self):
        bad = {**RESULT, "escalation": True, "missing_or_risky": ["Phone invalid.", "Address missing."]}
        wts.write_order_result(ORDER, bad)
        col = wts._build_col_index(self.ws)
        row = self.ws.appended[0]
        self.assertEqual(row[col["Escalation Required"] - 1], "YES")
        self.assertEqual(row[col["Escalation Reason"] - 1], "Phone invalid.; Address missing.")

    def test_send_result_fills_the_whatsapp_columns_only_when_provided(self):
        send_result = {"sent": True, "timestamp": "2026-11-11 03:00 UTC", "message_id": "wamid.X"}
        wts.write_order_result(ORDER, RESULT, send_result=send_result)
        col = wts._build_col_index(self.ws)
        row = self.ws.appended[0]
        self.assertEqual(row[col["WhatsApp Message Sent"] - 1], "Yes")
        self.assertEqual(row[col["WhatsApp Sent Time"] - 1], "2026-11-11 03:00 UTC")
        self.assertEqual(row[col["Meta Message ID"] - 1], "wamid.X")
        self.assertTrue(wts.write_order_result(ORDER, RESULT)["ok"])

    def test_matching_order_id_updates_in_place_instead_of_appending(self):
        col = wts._build_col_index(self.ws)
        existing = [""] * len(HEADER)
        existing[col["Order ID"] - 1] = "BSO-1001"
        existing[col["Internal Notes"] - 1] = "do not touch"
        self.ws = FakeWorksheet(data_rows=[existing])
        self.patcher.stop()
        self.patcher = patch.object(wts, "_open_sheet", return_value=self.ws)
        self.patcher.start()

        out = wts.write_order_result(ORDER, RESULT, order_id="BSO-1001")
        self.assertEqual(out["action"], "updated")
        self.assertEqual(out["row"], wts.DATA_START)
        self.assertFalse(self.ws.appended)
        updated_cols = {c for _, c, _ in self.ws.updates}
        self.assertNotIn(col["Internal Notes"], updated_cols)

    def test_unmatched_order_id_appends_a_new_row(self):
        out = wts.write_order_result(ORDER, RESULT, order_id="BSO-9999")
        self.assertEqual(out["action"], "appended")

    def test_connection_failure_is_reported_not_raised(self):
        with patch.object(wts, "_open_sheet", side_effect=RuntimeError("GOOGLE_SHEETS_ID is not set in .env.")):
            out = wts.write_order_result(ORDER, RESULT)
        self.assertFalse(out["ok"])
        self.assertIn("GOOGLE_SHEETS_ID", out["reason"])


class TestConnectionTests(unittest.TestCase):
    def test_reports_headers_and_title_on_success(self):
        with patch.object(wts, "_open_sheet", return_value=FakeWorksheet()):
            r = wts.test_connection()
        self.assertTrue(r["ok"])
        self.assertEqual(r["title"], wts.SHEET_NAME)
        self.assertEqual(r["count"], len(HEADER))

    def test_reports_failure_reason_without_raising(self):
        with patch.object(wts, "_open_sheet", side_effect=RuntimeError("no credentials configured")):
            r = wts.test_connection()
        self.assertFalse(r["ok"])
        self.assertIn("no credentials", r["reason"])


class SendWhatsappMessageTests(unittest.TestCase):
    def setUp(self):
        self._orig_live = swm._LIVE

    def tearDown(self):
        swm._LIVE = self._orig_live

    def test_invalid_phone_is_rejected_before_any_send_attempt(self):
        r = swm.send_whatsapp_message("not-a-number", "hello")
        self.assertFalse(r["sent"])
        self.assertIn("Invalid international phone", r["error"])

    def test_dry_run_when_not_live_returns_sent_true_without_a_network_call(self):
        swm._LIVE = False
        r = swm.send_whatsapp_message("971501234567", "Order confirmed.")
        self.assertTrue(r["sent"])
        self.assertTrue(r["dry_run"])
        self.assertEqual(r["message_id"], "DRY_RUN")
        self.assertEqual(r["error"], "")

    def test_live_send_parses_the_meta_message_id(self):
        swm._LIVE = True
        fake_resp = MagicMock()
        fake_resp.read.return_value = json.dumps({"messages": [{"id": "wamid.ABC"}]}).encode("utf-8")
        fake_resp.__enter__.return_value = fake_resp
        fake_resp.__exit__.return_value = False
        with patch("urllib.request.urlopen", return_value=fake_resp):
            r = swm.send_whatsapp_message("971501234567", "Order confirmed.")
        self.assertTrue(r["sent"])
        self.assertFalse(r["dry_run"])
        self.assertEqual(r["message_id"], "wamid.ABC")

    def test_live_send_failure_is_reported_not_raised(self):
        swm._LIVE = True
        with patch("urllib.request.urlopen", side_effect=OSError("network unreachable")):
            r = swm.send_whatsapp_message("971501234567", "Order confirmed.")
        self.assertFalse(r["sent"])
        self.assertIn("network unreachable", r["error"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
