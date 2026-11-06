"""Offline authorization regressions. No real login, Sheets or credentials."""
import ast
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from ops.auth import (
    OWNER, SALES, PACKING, COURIER, resolve_role, current_role,
    authorize_update, can_perform_action, require_access,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY = {"issuer": "https://id.example.test", "user_roles": {"subject-1": SALES}}
CLAIMS = {"iss": "https://id.example.test", "sub": "subject-1"}


class User(dict):
    is_logged_in = True


class AuthTests(unittest.TestCase):
    def test_authorized_verified_subject(self):
        self.assertEqual(resolve_role(CLAIMS, POLICY, logged_in=True), SALES)

    def test_unverified_identity_denied(self):
        for logged_in in (False, None, "true", 1):
            self.assertIsNone(resolve_role(CLAIMS, POLICY, logged_in=logged_in))

    def test_unmapped_or_invalid_claims_denied(self):
        for claims in ({}, {"iss": "other", "sub": "subject-1"},
                       {"iss": CLAIMS["iss"], "sub": "unknown"},
                       {"iss": CLAIMS["iss"], "sub": []},
                       {"email": "owner@example.test"}, None):
            with self.subTest(claims=claims):
                self.assertIsNone(resolve_role(claims, POLICY, logged_in=True))

    def test_missing_invalid_and_unknown_policy_denied(self):
        for policy in ({}, None, {"issuer": CLAIMS["iss"]},
                       {"issuer": CLAIMS["iss"], "user_roles": {"subject-1": "Super Admin"}},
                       {"issuer": CLAIMS["iss"], "user_roles": {"subject-1": []}}):
            self.assertIsNone(resolve_role(CLAIMS, policy, logged_in=True))

    def test_all_configured_roles_supported(self):
        for role in (OWNER, SALES, PACKING, COURIER, "Read Only"):
            policy = {**POLICY, "user_roles": {"subject-1": role}}
            self.assertEqual(resolve_role(CLAIMS, policy, logged_in=True), role)

    def test_session_role_and_user_claim_cannot_escalate(self):
        fake = types.SimpleNamespace(user=User({**CLAIMS, "role": OWNER}),
                                     secrets={"ops_auth": POLICY},
                                     session_state={"role": OWNER})
        with patch.dict(sys.modules, {"streamlit": fake}):
            self.assertEqual(current_role(), SALES)
            fake.secrets = {"ops_auth": {}}
            self.assertIsNone(current_role())

    def test_no_streamlit_identity_denies(self):
        with patch.dict(sys.modules, {"streamlit": types.SimpleNamespace()}):
            self.assertIsNone(current_role())

    def test_denied_page_stops(self):
        fake = types.SimpleNamespace(
            user=User({}), secrets={}, error=lambda *_: None, info=lambda *_: None,
            button=lambda *a, **kw: False, stop=lambda: None,
        )
        with patch.dict(sys.modules, {"streamlit": fake}), self.assertRaises(PermissionError):
            require_access()

    def test_read_only_and_unknown_roles_never_write(self):
        for role in (None, "Read Only", "arbitrary"):
            for resource in ("Master Orders", "Payments", "Packing QC", "Courier Tracking"):
                with self.assertRaises(PermissionError):
                    authorize_update(role, resource, {"Order Status": "Delivered"})

    def test_cross_role_master_field_writes_denied(self):
        for role, changes in (
            (PACKING, {"Payment Status": "Paid Online"}),
            (COURIER, {"Payment Status": "Paid Online"}),
            (SALES, {"Proof of Delivery": "fabricated"}),
            (SALES, {"Packing QC Status": "Passed"}),
            (PACKING, {"Courier Status": "Delivered"}),
            (SALES, {"Risk Status": "Low"}),
            (PACKING, {"Last Updated": "fabricated"}),
            (COURIER, {"Unrecognized Field": "x"}),
        ):
            with self.subTest(role=role, changes=changes), self.assertRaises(PermissionError):
                authorize_update(role, "Master Orders", changes)

    def test_cross_role_workflow_state_denied(self):
        for role, state in ((COURIER, "Paid Online"), (PACKING, "Closed Successfully"),
                            (SALES, "Delivered"), (PACKING, "Unknown")):
            with self.assertRaises(PermissionError):
                authorize_update(role, "Master Orders", {"Order Status": state})

    def test_role_appropriate_updates_allowed(self):
        for role, changes in (
            (SALES, {"Order Status": "Paid Online", "Payment Status": "Paid Online", "COD Expected": "0"}),
            (SALES, {"Order Status": "QC Pending", "Packing QC Status": "Pending"}),
            (SALES, {"Order Status": "Issue / Return", "Risk Status": "High"}),
            (PACKING, {"Order Status": "Shipment Label Ready", "Shipment Label Status": "Ready to Print"}),
            (PACKING, {"Order Status": "Courier Booked", "Courier Status": "Booked"}),
            (COURIER, {"Order Status": "Delivered", "Proof of Delivery": "synthetic"}),
            (OWNER, {"Risk Status": "Low"}),
        ):
            authorize_update(role, "Master Orders", changes)

    def test_worksheet_writes_role_scoped(self):
        for resource, allowed, field in (("Payments", SALES, "Notes"), ("Packing QC", PACKING, "QC Notes"),
                                         ("Courier Tracking", COURIER, "Courier Notes")):
            for role in (OWNER, SALES, PACKING, COURIER):
                if role in (OWNER, allowed):
                    authorize_update(role, resource, {field: "synthetic"})
                else:
                    with self.assertRaises(PermissionError):
                        authorize_update(role, resource, {field: "synthetic"})
        with self.assertRaises(PermissionError):
            authorize_update(OWNER, "Unknown worksheet", {"Notes": "x"})

    def test_worksheet_identifiers_and_unknown_fields_denied(self):
        for resource, role in (("Payments", SALES), ("Packing QC", PACKING),
                               ("Courier Tracking", COURIER)):
            for field in ("Order ID", "Last Updated", "Unknown Column"):
                with self.assertRaises(PermissionError):
                    authorize_update(role, resource, {field: "synthetic"})

    def test_empty_or_invalid_updates_denied(self):
        for changes in ({}, None, []):
            with self.assertRaises(PermissionError):
                authorize_update(OWNER, "Master Orders", changes)

    def test_action_buttons_match_roles(self):
        self.assertTrue(can_perform_action(SALES, "Mark Paid Online"))
        self.assertTrue(can_perform_action(PACKING, "Mark Packed"))
        self.assertTrue(can_perform_action(COURIER, "Mark Delivered"))
        for role in (None, "Read Only", PACKING, COURIER):
            self.assertFalse(can_perform_action(role, "Mark Paid Online"))
        self.assertFalse(can_perform_action(SALES, "unknown action"))

    def test_each_page_gates_before_cached_data(self):
        for path in [ROOT / "ops_app.py", *sorted((ROOT / "pages").glob("*.py"))]:
            source = path.read_text()
            tree = ast.parse(source)
            calls = [(node.func.id, node.lineno) for node in ast.walk(tree)
                     if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
            guards = [line for name, line in calls if name == "require_access"]
            self.assertEqual(len(guards), 1, path.name)
            for name, line in calls:
                if name.startswith("get_") or name in ("load", "load_orders"):
                    self.assertLess(guards[0], line, path.name)
            self.assertNotIn('session_state.get("role"', source)
            self.assertNotIn('session_state["role"]', source)

    def test_write_boundary_denies_before_sheet_io(self):
        from ops import sheets
        helpers = (sheets.update_master_order, sheets.update_payment,
                   sheets.update_packing_qc, sheets.update_courier)
        with patch("ops.auth.current_role", return_value="Read Only"), patch.object(sheets, "_ws") as ws:
            for helper in helpers:
                with self.assertRaises(PermissionError):
                    helper("synthetic-order", {"Order Status": "Delivered"})
            ws.assert_not_called()

    def test_unauthenticated_read_denied_before_connection(self):
        from ops import sheets
        with patch("ops.auth.current_role", return_value=None), patch.object(sheets, "_connect") as connect:
            with self.assertRaises(PermissionError):
                sheets.get_master_orders()
            connect.assert_not_called()

    def test_cached_connection_does_not_bypass_auth(self):
        from ops import sheets
        with patch("ops.auth.current_role", return_value=None), patch.object(sheets, "_wb", object()):
            with self.assertRaises(PermissionError):
                sheets._connect()


if __name__ == "__main__":
    unittest.main()
