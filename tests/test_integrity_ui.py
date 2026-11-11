"""Synthetic Streamlit shortcut/form regressions; all Sheets access is faked."""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit import cache_data
from streamlit.testing.v1 import AppTest

from test_integrity import FakeWorkbook, MASTER, ORDER_ID

ROOT = Path(__file__).resolve().parents[1]


class IntegrityPageTests(unittest.TestCase):
    def setUp(self):
        cache_data.clear()
        self.book = FakeWorkbook()
        self.connection = patch("ops.sheets._connect", return_value=self.book)
        self.connection.start()
        self.addCleanup(self.connection.stop)
        self.addCleanup(cache_data.clear)

    def page(self, filename, role="Owner / Admin", visible=None, fresh_reads=False):
        visible = deepcopy(MASTER) if visible is None else visible
        app = AppTest.from_file(str(ROOT / "pages" / filename))
        app.user = {"is_logged_in": True, "iss": "https://id.example.test", "sub": "synthetic-subject"}
        app.secrets["ops_auth"] = {"issuer": "https://id.example.test", "user_roles": {"synthetic-subject": role}}
        orders = (patch("ops.sheets.get_master_orders", side_effect=lambda: pd.DataFrame([self.book.sheets["Master Orders"].record()]))
                  if fresh_reads else patch("ops.sheets.get_master_orders", return_value=pd.DataFrame([visible])))
        courier = patch("ops.sheets.get_courier_tracking", return_value=pd.DataFrame())
        payments = patch("ops.sheets.get_payments", return_value=pd.DataFrame([self.book.sheets["Payments"].record()]))
        for mock in (orders, courier, payments):
            mock.start()
            self.addCleanup(mock.stop)
        app.run()
        self.assertEqual(len(app.exception), 0)
        return app

    def click(self, app, text):
        matches = [button for button in app.button if button.label == text]
        self.assertEqual(len(matches), 1, [button.label for button in app.button])
        matches[0].click().run()
        self.assertEqual(len(app.exception), 0)

    def test_pod_shortcut_missing_evidence_cannot_write(self):
        self.book.sheets["Master Orders"].change("Proof of Delivery", "")
        visible = self.book.sheets["Master Orders"].record()
        app = self.page("5_Courier.py", "Courier / Delivery", visible)
        self.click(app, "📬 POD Received")
        self.assertEqual(self.book.calls, [])
        self.assertTrue(any("Proof of Delivery" in error.value for error in app.error))
        self.assertEqual(len(app.success), 0)

    def test_pod_shortcut_uses_new_form_evidence_and_one_batch(self):
        self.book.sheets["Master Orders"].change("Proof of Delivery", "")
        app = self.page("5_Courier.py", "Courier / Delivery", self.book.sheets["Master Orders"].record())
        next(area for area in app.text_area if area.label.startswith("Proof of Delivery")).set_value("new synthetic proof")
        self.click(app, "📬 POD Received")
        self.assertEqual(len(self.book.calls), 1)
        record = self.book.sheets["Master Orders"].record()
        self.assertEqual(record["Order Status"], "POD Received")
        self.assertEqual(record["Proof of Delivery"], "new synthetic proof")

    def test_full_delivery_form_rejects_same_missing_evidence(self):
        app = self.page("5_Courier.py", "Courier / Delivery")
        next(area for area in app.text_area if area.label.startswith("Proof of Delivery")).set_value("")
        next(box for box in app.selectbox if box.label == "Delivery Status" and "All" not in box.options).select("Delivered")
        self.click(app, "💾 Save Delivery Update")
        self.assertEqual(self.book.calls, [])
        self.assertTrue(any("Proof of Delivery" in error.value for error in app.error))

    def test_orders_shortcut_rechecks_fresh_sheet_not_cached_evidence(self):
        app = self.page("1_Orders.py", "Courier / Delivery")
        self.book.sheets["Master Orders"].change("Staff Number", "")
        self.click(app, "Mark Delivered")
        self.assertEqual(self.book.calls, [])
        self.assertTrue(any("Staff Number" in error.value for error in app.error))

    def test_orders_closeout_cannot_skip_satisfaction_requirement(self):
        visible = {**MASTER, "Order Status": "Review Requested", "Delivery Status": "Delivered",
                   "Customer Satisfaction Score": ""}
        ws = self.book.sheets["Master Orders"]
        for field in ("Order Status", "Delivery Status", "Customer Satisfaction Score"):
            ws.change(field, visible[field])
        app = self.page("1_Orders.py", "Sales / WhatsApp", visible)
        self.click(app, "Close Successfully")
        self.assertEqual(self.book.calls, [])
        self.assertTrue(any("Customer Satisfaction Score" in error.value for error in app.error))

    def test_repeated_pod_action_is_a_complete_idempotent_write(self):
        app = self.page("5_Courier.py", "Courier / Delivery")
        self.click(app, "📬 POD Received")
        first = self.book.sheets["Master Orders"].record()
        self.click(app, "📬 POD Received")
        second = self.book.sheets["Master Orders"].record()
        self.assertEqual(len(self.book.calls), 2)
        first.pop("Last Updated")
        second.pop("Last Updated")
        self.assertEqual(first, second)

    def test_payment_form_saves_both_records_in_one_batch(self):
        app = self.page("2_Payments.py", "Sales / WhatsApp")
        next(box for box in app.selectbox if box.label == "Payment Status" and "All" not in box.options).select("Paid Online")
        self.click(app, "💾 Save Payment Update")
        self.assertEqual(len(self.book.calls), 1)
        for resource in ("Master Orders", "Payments"):
            self.assertEqual(self.book.sheets[resource].record()["Payment Status"], "Paid Online")
            self.assertEqual(self.book.sheets[resource].record()["COD Expected"], "0")

    def test_lost_response_clears_cache_before_operator_refresh(self):
        app = self.page("5_Courier.py", "Courier / Delivery", fresh_reads=True)
        self.book.failure = "lost-response"
        with patch.object(cache_data, "clear", wraps=cache_data.clear) as clear:
            self.click(app, "📬 POD Received")
            clear.assert_called_once()
        self.assertEqual(len(app.success), 0)
        self.assertTrue(any("not confirmed" in error.value for error in app.error))
        self.assertEqual(len(self.book.calls), 1)
        app.run()  # Explicit operator refresh, not an automatic write retry.
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.dataframe[0].value.iloc[0]["Order Status"], "POD Received")
        self.assertEqual(len(self.book.calls), 1)

    def test_payment_batch_failure_never_shows_success_or_writes_partial(self):
        app = self.page("2_Payments.py", "Sales / WhatsApp")
        next(box for box in app.selectbox if box.label == "Payment Status" and "All" not in box.options).select("Paid Online")
        self.book.failure = "reject"
        before = self.book.snapshot()
        self.click(app, "💾 Save Payment Update")
        self.assertEqual(self.book.snapshot(), before)
        self.assertEqual(len(self.book.calls), 1)
        self.assertEqual(len(app.success), 0)
        self.assertTrue(any("not confirmed" in error.value for error in app.error))


if __name__ == "__main__":
    unittest.main()
