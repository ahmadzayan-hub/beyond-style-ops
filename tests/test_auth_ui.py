"""Local Streamlit entry-point regressions with synthetic identities/data only."""
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
PAGES = [ROOT / "ops_app.py", *sorted((ROOT / "pages").glob("*.py"))]
POLICY = {"issuer": "https://id.example.test", "user_roles": {"subject-1": "Read Only"}}


class PageAccessTests(unittest.TestCase):
    def test_anonymous_direct_pages_never_read_sheets(self):
        with patch("ops.sheets._connect", side_effect=AssertionError("Unauthorized sheet access")) as connect:
            for page in PAGES:
                with self.subTest(page=page.name):
                    app = AppTest.from_file(str(page)).run()
                    self.assertEqual(len(app.exception), 0)
                    self.assertEqual(len(app.error), 1)
                    self.assertEqual(len(app.dataframe), 0)
            connect.assert_not_called()

    def test_unmapped_authenticated_direct_pages_deny(self):
        with patch("ops.sheets._connect", side_effect=AssertionError("Unauthorized sheet access")) as connect:
            for page in PAGES:
                with self.subTest(page=page.name):
                    app = AppTest.from_file(str(page))
                    app.user = {"is_logged_in": True, "iss": POLICY["issuer"], "sub": "unmapped"}
                    app.secrets["ops_auth"] = POLICY
                    app.session_state["role"] = "Owner / Admin"
                    app.run()
                    self.assertEqual(len(app.exception), 0)
                    self.assertEqual(len(app.error), 1)
                    self.assertEqual(len(app.dataframe), 0)
            connect.assert_not_called()

    def test_verified_read_only_subject_reaches_mocked_data(self):
        with patch("ops.sheets.get_master_orders", return_value=pd.DataFrame()) as orders, \
             patch("ops.sheets.get_payments", return_value=pd.DataFrame()), \
             patch("ops.sheets.get_courier_tracking", return_value=pd.DataFrame()):
            for page in PAGES:
                with self.subTest(page=page.name):
                    app = AppTest.from_file(str(page))
                    app.user = {"is_logged_in": True, "iss": POLICY["issuer"], "sub": "subject-1"}
                    app.secrets["ops_auth"] = POLICY
                    app.session_state["role"] = "Owner / Admin"
                    app.run()
                    self.assertEqual(len(app.exception), 0)
                    self.assertEqual(len(app.error), 0)
                    self.assertTrue(any(button.label == "Sign out" for button in app.button))
            self.assertTrue(orders.called)

    def test_revocation_blocks_previously_cached_data(self):
        from streamlit import cache_data
        cache_data.clear()
        synthetic_orders = pd.DataFrame([{
            "Order ID": "synthetic-private-order", "Customer Name": "Synthetic Customer",
            "Order Status": "New Form Order", "Payment Status": "Payment Pending",
        }])
        with patch("ops.sheets.get_master_orders", return_value=synthetic_orders):
            app = AppTest.from_file(str(ROOT / "ops_app.py"))
            app.user = {"is_logged_in": True, "iss": POLICY["issuer"], "sub": "subject-1"}
            app.secrets["ops_auth"] = POLICY
            app.run()
            self.assertEqual(len(app.error), 0)
            self.assertGreater(len(app.dataframe), 0)
            app.secrets["ops_auth"] = {"issuer": POLICY["issuer"], "user_roles": {}}
            app.run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(len(app.error), 1)
            self.assertEqual(len(app.dataframe), 0)


if __name__ == "__main__":
    unittest.main()
