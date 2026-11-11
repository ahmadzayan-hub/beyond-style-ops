"""Synthetic-only, offline validation and atomic request regressions."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from ops import sheets
from ops.auth import OWNER, SALES, PACKING, COURIER
from ops.integrity import DELIVERY_EVIDENCE, UpdateValidationError, validate_order_update

ORDER_ID = "synthetic-order-1"
EVIDENCE = {"Receiver Name": "Synthetic Receiver", "Staff Number": "N/A",
            "Actual Received Date": "2026-01-01", "Proof of Delivery": "synthetic proof"}
MASTER = {"Order ID": ORDER_ID, "Order Status": "Out for Delivery",
          "Delivery Status": "Out for Delivery", "Courier Status": "Out for Delivery",
          **EVIDENCE, "Last Updated": "before", "Internal Notes": "keep this",
          "Packing QC Status": "Passed", "Shipment Label Status": "",
          "Customer Satisfaction Score": "5 Very Happy", "Payment Status": "Payment Pending",
          "COD Expected": "10", "Courier Company": "Synthetic Courier", "AWB / Tracking Number": "test-awb",
          "Courier Notes": "", "Customer Name": "Synthetic Customer", "Product Summary": "Synthetic Product"}
PAYMENT = {"Order ID": ORDER_ID, "Payment Status": "Payment Pending", "Payment Reference": "",
           "Payment Link": "", "COD Expected": "10", "COD Collected": "", "Notes": "", "Last Updated": "before"}


class FakeWorksheet:
    def __init__(self, name, sheet_id, record):
        self.name, self.id = name, sheet_id
        self.head_row = 3 if name == "Master Orders" else 1
        self.rows = [["title"]] * (self.head_row - 1) + [list(record), list(record.values())]
        self.reads = 0

    def get_all_values(self):
        self.reads += 1
        return deepcopy(self.rows)

    def record(self):
        return dict(zip(self.rows[self.head_row - 1], self.rows[self.head_row]))

    def change(self, field, value):
        col = self.rows[self.head_row - 1].index(field)
        self.rows[self.head_row][col] = value

    def update_cell(self, *_):
        raise AssertionError("Per-cell network writes must never be used")


class FakeWorkbook:
    """Emulates the documented atomic batch contract; never connects anywhere."""
    def __init__(self):
        self.sheets = {
            "Master Orders": FakeWorksheet("Master Orders", 100, MASTER),
            "Payments": FakeWorksheet("Payments", 200, PAYMENT),
            "Courier Tracking": FakeWorksheet("Courier Tracking", 300, {"Order ID": ORDER_ID, **EVIDENCE,
                                                                        "Delivery Status": "Out for Delivery"}),
            "Packing QC": FakeWorksheet("Packing QC", 400, {"Order ID": ORDER_ID, "Packing QC Status": "Pending"}),
        }
        self.calls = []
        self.failure = None

    def worksheet(self, name):
        return self.sheets[name]

    def snapshot(self):
        return {name: deepcopy(ws.rows) for name, ws in self.sheets.items()}

    def batch_update(self, body):
        self.calls.append(deepcopy(body))
        pending = self.snapshot()
        for request in body["requests"]:
            cell = request["updateCells"]
            self.assert_field_mask(cell)
            start = cell["start"]
            name = next(name for name, ws in self.sheets.items() if ws.id == start["sheetId"])
            pending[name][start["rowIndex"]][start["columnIndex"]] = cell["rows"][0]["values"][0]["userEnteredValue"]["stringValue"]
        if self.failure == "reject":
            raise RuntimeError("synthetic late batch validation failure")
        for name, rows in pending.items():
            self.sheets[name].rows = rows
        if self.failure == "lost-response":
            raise TimeoutError("synthetic response lost after server commit")
        return {"replies": [{} for _ in body["requests"]]}

    @staticmethod
    def assert_field_mask(cell):
        if cell["fields"] != "userEnteredValue":
            raise AssertionError("Do not overwrite formatting or other fields")


class ValidationTests(unittest.TestCase):
    def test_every_evidence_field_required_for_each_delivered_status(self):
        for status_field in ("Order Status", "Delivery Status", "Courier Status"):
            statuses = ("Delivered",) if status_field == "Courier Status" else ("Delivered", "POD Received")
            for status in statuses:
                for field in DELIVERY_EVIDENCE:
                    for missing in ("", " \t", None, float("nan")):
                        with self.subTest(status_field=status_field, status=status, field=field, missing=missing):
                            with self.assertRaises(UpdateValidationError):
                                validate_order_update({**MASTER, field: missing}, {status_field: status})

    def test_full_form_can_supply_evidence_with_transition(self):
        current = {**MASTER, **dict.fromkeys(DELIVERY_EVIDENCE, "")}
        validate_order_update(current, {**EVIDENCE, "Delivery Status": "POD Received", "Order Status": "POD Received"})

    def test_evidence_cannot_be_cleared_after_delivery_or_closeout(self):
        for status in ("Delivered", "POD Received", "Closed Successfully"):
            for field in DELIVERY_EVIDENCE:
                with self.assertRaises(UpdateValidationError):
                    validate_order_update({**MASTER, "Order Status": status, "Delivery Status": "Delivered"}, {field: ""})

    def test_closeout_uses_all_review_form_requirements(self):
        good = {**MASTER, "Delivery Status": "Delivered"}
        validate_order_update(good, {"Order Status": "Closed Successfully"})
        for field in (*DELIVERY_EVIDENCE, "Delivery Status", "Customer Satisfaction Score"):
            with self.subTest(field=field), self.assertRaises(UpdateValidationError):
                validate_order_update({**good, field: ""}, {"Order Status": "Closed Successfully"})

    def test_label_checks_merged_qc(self):
        with self.assertRaises(UpdateValidationError):
            validate_order_update({**MASTER, "Packing QC Status": "Failed"}, {"Shipment Label Status": "Ready to Print"})
        validate_order_update({**MASTER, "Packing QC Status": "Pending"},
                              {"Packing QC Status": "Passed", "Order Status": "Shipment Label Ready"})

    def test_unrelated_predelivery_edits_do_not_require_evidence(self):
        validate_order_update({**MASTER, **dict.fromkeys(DELIVERY_EVIDENCE, "")}, {"Internal Notes": "synthetic"})


class AtomicWriteTests(unittest.TestCase):
    def setUp(self):
        self.book = FakeWorkbook()
        self.role = patch("ops.auth.current_role", return_value=OWNER)
        self.connection = patch.object(sheets, "_connect", return_value=self.book)
        self.role.start()
        self.connection.start()
        self.addCleanup(self.role.stop)
        self.addCleanup(self.connection.stop)

    def test_single_atomic_request_preserves_other_cells(self):
        changes = {"Order Status": "POD Received", "Delivery Status": "POD Received"}
        self.assertTrue(sheets.update_master_order(ORDER_ID, changes))
        self.assertEqual(changes, {"Order Status": "POD Received", "Delivery Status": "POD Received"})
        self.assertEqual(len(self.book.calls), 1)
        self.assertEqual(len(self.book.calls[0]["requests"]), 3)
        current = self.book.sheets["Master Orders"].record()
        self.assertEqual(current["Internal Notes"], "keep this")
        self.assertNotEqual(current["Last Updated"], "before")

    def test_missing_fresh_evidence_prevents_all_writes(self):
        self.book.sheets["Master Orders"].change("Proof of Delivery", "")
        before = self.book.snapshot()
        result = sheets.update_master_order(ORDER_ID, {"Delivery Status": "POD Received", "Order Status": "POD Received"})
        self.assertFalse(result)
        self.assertIn("Proof of Delivery", result.message)
        self.assertEqual(self.book.snapshot(), before)
        self.assertEqual(self.book.calls, [])

    def test_new_evidence_and_status_saved_together(self):
        self.book.sheets["Master Orders"].change("Proof of Delivery", "")
        self.assertTrue(sheets.update_master_order(ORDER_ID, {**EVIDENCE, "Delivery Status": "Delivered"}))
        self.assertEqual(len(self.book.calls), 1)

    def test_missing_or_duplicate_requested_header_fails_before_writes(self):
        for resource in ("Master Orders", "Payments"):
            for field in ("Order ID", "Payment Status", "Last Updated"):
                for duplicate in (False, True):
                    self.book = FakeWorkbook()
                    self.connection.stop()
                    self.connection = patch.object(sheets, "_connect", return_value=self.book)
                    self.connection.start()
                    ws = self.book.sheets[resource]
                    headers = ws.rows[ws.head_row - 1]
                    if duplicate:
                        headers.append(field)
                    else:
                        headers[headers.index(field)] = "Renamed Header"
                    with self.subTest(resource=resource, field=field, duplicate=duplicate):
                        self.assertFalse(sheets.update_order_records(ORDER_ID, {resource: {"Payment Status": "Paid Online"}}))
                        self.assertEqual(self.book.calls, [])
        self.addCleanup(self.connection.stop)

    def test_blank_missing_duplicate_and_header_order_ids_fail_closed(self):
        for oid in ("", None, "missing", "Order ID"):
            self.assertFalse(sheets.update_master_order(oid, {"Internal Notes": "x"}))
        ws = self.book.sheets["Master Orders"]
        ws.rows.append(deepcopy(ws.rows[-1]))
        self.assertFalse(sheets.update_master_order(ORDER_ID, {"Internal Notes": "x"}))
        self.assertEqual(self.book.calls, [])

    def test_payment_and_master_share_one_atomic_request(self):
        result = sheets.update_payment_and_master(ORDER_ID,
            {"Payment Status": "Paid Online", "COD Expected": "0"},
            {"Payment Status": "Paid Online", "Order Status": "Paid Online", "COD Expected": "0"})
        self.assertTrue(result)
        self.assertEqual(len(self.book.calls), 1)
        self.assertEqual({r["updateCells"]["start"]["sheetId"] for r in self.book.calls[0]["requests"]}, {100, 200})
        for resource in ("Master Orders", "Payments"):
            self.assertEqual(self.book.sheets[resource].record()["Payment Status"], "Paid Online")

    def test_bad_secondary_record_prevents_both_writes(self):
        for missing in ("Payments", "Master Orders"):
            book = FakeWorkbook()
            book.sheets[missing].rows.pop()
            with patch.object(sheets, "_connect", return_value=book):
                before = book.snapshot()
                result = sheets.update_payment_and_master(ORDER_ID, {"Payment Status": "Paid Online"}, {"Payment Status": "Paid Online"})
                self.assertFalse(result)
                self.assertEqual(book.snapshot(), before)
                self.assertEqual(book.calls, [])

    def test_batch_rejection_cannot_leave_partial_sheet_or_cell_updates(self):
        self.book.failure = "reject"
        before = self.book.snapshot()
        result = sheets.update_payment_and_master(ORDER_ID, {"Payment Status": "Paid Online"},
                                                {"Payment Status": "Paid Online", "Order Status": "Paid Online"})
        self.assertFalse(result)
        self.assertEqual(len(self.book.calls), 1)
        self.assertEqual(self.book.snapshot(), before)

    def test_uncertain_committed_response_is_not_retried_or_claimed_failed(self):
        self.book.failure = "lost-response"
        result = sheets.update_master_order(ORDER_ID, {"Internal Notes": "changed"})
        self.assertFalse(result)
        self.assertTrue(result.uncertain)
        self.assertIn("not confirmed", result.message)
        self.assertEqual(self.book.sheets["Master Orders"].record()["Internal Notes"], "changed")
        self.assertEqual(len(self.book.calls), 1)

    def test_all_writers_use_batch_and_literal_values(self):
        for helper, field in ((sheets.update_master_order, "Internal Notes"), (sheets.update_payment, "Notes"),
                              (sheets.update_packing_qc, "Packing QC Status"), (sheets.update_courier, "Proof of Delivery")):
            with self.subTest(helper=helper.__name__):
                self.assertTrue(helper(ORDER_ID, {field: "=SYNTHETIC()"}))
                self.assertIn("stringValue", str(self.book.calls[-1]))
                self.assertNotIn("formulaValue", str(self.book.calls[-1]))
        self.assertEqual(len(self.book.calls), 4)

    def test_courier_tracking_cannot_bypass_delivery_evidence(self):
        self.book.sheets["Courier Tracking"].change("Receiver Name", "")
        self.assertFalse(sheets.update_courier(ORDER_ID, {"Delivery Status": "Delivered"}))
        self.assertEqual(self.book.calls, [])

    def test_revoked_access_during_preflight_cannot_write(self):
        with patch("ops.sheets.assert_update", side_effect=[None, PermissionError("revoked")]):
            with self.assertRaises(PermissionError):
                sheets.update_master_order(ORDER_ID, {"Internal Notes": "x"})
        self.assertEqual(self.book.calls, [])

    def test_every_resource_authorized_before_io(self):
        with patch("ops.auth.current_role", return_value=COURIER), patch.object(sheets, "_connect") as connect:
            with self.assertRaises(PermissionError):
                sheets.update_payment_and_master(ORDER_ID, {"Payment Status": "Paid Online"}, {"Payment Status": "Paid Online"})
            connect.assert_not_called()

    def test_read_error_does_not_expose_provider_details(self):
        with patch.object(self.book, "worksheet", side_effect=RuntimeError("sensitive provider payload")):
            result = sheets.update_master_order(ORDER_ID, {"Internal Notes": "x"})
        self.assertFalse(result)
        self.assertFalse(result.uncertain)
        self.assertNotIn("sensitive", result.message)
        self.assertEqual(self.book.calls, [])


if __name__ == "__main__":
    unittest.main()
