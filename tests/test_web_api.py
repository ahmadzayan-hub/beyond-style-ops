"""
test_web_api.py  -  tests the Vercel web API (api/index.py) with the Google Sheet replaced by
fakes, so no credentials are needed. Run:  python tests/test_web_api.py
"""

import importlib.util
import os
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "execution"))

os.environ["APP_PASSWORD"] = "test-password-123"
os.environ["SESSION_SECRET"] = "test-session-secret"

from ops import sheets, web_auth  # noqa: E402
from ops.payments import PaymentRuleError, build_payment_updates  # noqa: E402

_spec = importlib.util.spec_from_file_location("web_api", ROOT / "api" / "index.py")
web_api = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(web_api)

from fastapi.testclient import TestClient  # noqa: E402

ORDERS = pd.DataFrame([
    {"Order ID": "BS-1001", "Customer Name": "Fatima Al Marri", "Mobile Number": "0501234567",
     "Emirate": "Dubai", "Order Status": "Payment Pending", "Payment Status": "Payment Pending",
     "Risk Status": "Low", "Total Amount": "104", "Order Date": "2026-10-20"},
    {"Order ID": "BS-1002", "Customer Name": "<script>alert(1)</script>", "Mobile Number": "0559876543",
     "Emirate": "Sharjah", "Order Status": "Customer Approved", "Payment Status": "",
     "Risk Status": "High", "Total Amount": "", "Order Date": "2026-10-21"},
])


class FakeSheets:
    """Records writes. Read results and write outcomes are set per test."""

    def __init__(self):
        self.master_writes = []
        self.payment_writes = []
        self.master_ok = True
        self.payment_ok = True
        self.payments_df = pd.DataFrame(columns=["Order ID", "Payment Status"])
        self.fail_reads = False

    def get_master_orders(self):
        if self.fail_reads:
            raise RuntimeError("sheet exploded: credential detail")
        return ORDERS.copy()

    def get_payments(self):
        if self.fail_reads:
            raise RuntimeError("sheet exploded: credential detail")
        return self.payments_df.copy()

    def update_master_order(self, order_id, updates):
        self.master_writes.append((order_id, dict(updates)))
        return self.master_ok

    def update_payment(self, order_id, updates):
        self.payment_writes.append((order_id, dict(updates)))
        return self.payment_ok


FAILURES = []
PASSES = []


def check(name, condition, detail=""):
    if condition:
        PASSES.append(name)
    else:
        FAILURES.append(f"{name}: {detail}")


def fresh_client(fake):
    sheets.get_master_orders = fake.get_master_orders
    sheets.get_payments = fake.get_payments
    sheets.update_master_order = fake.update_master_order
    sheets.update_payment = fake.update_payment
    web_api._orders_cache["rows"] = None
    return TestClient(web_api.app, base_url="https://testserver")


def signed_in(client):
    res = client.post("/api/login", json={"password": "test-password-123"})
    assert res.status_code == 200, res.text
    return client


def run():
    # ── Auth gate ─────────────────────────────────────────────────────────────
    fake = FakeSheets()
    client = fresh_client(fake)

    check("unauthenticated orders are refused", client.get("/api/orders").status_code == 401)
    check("unauthenticated payment save is refused",
          client.post("/api/payments/BS-1001", json={"status": "Paid Online"}).status_code == 401)
    check("session reports signed out", client.get("/api/session").json() == {"authenticated": False})

    check("wrong password is refused",
          client.post("/api/login", json={"password": "nope"}).status_code == 401)

    res = client.post("/api/login", json={"password": "test-password-123"})
    cookie_header = res.headers.get("set-cookie", "").lower()
    check("correct password signs in", res.status_code == 200)
    check("session cookie is HttpOnly", "httponly" in cookie_header, cookie_header)
    check("session cookie is Secure", "secure" in cookie_header, cookie_header)
    check("session cookie is SameSite=Strict", "samesite=strict" in cookie_header, cookie_header)

    # ── Read routes ───────────────────────────────────────────────────────────
    orders = client.get("/api/orders")
    check("signed-in orders load", orders.status_code == 200)
    rows = orders.json()["orders"]
    check("orders return every sheet row", len(rows) == 2, str(len(rows)))
    check("customer text returned as data", rows[1]["Customer Name"] == "<script>alert(1)</script>")
    check("API responses are no-store", orders.headers.get("cache-control") == "no-store",
          orders.headers.get("cache-control", ""))
    check("unknown order is 404", client.get("/api/orders/BS-9999").status_code == 404)
    check("known order is returned",
          client.get("/api/orders/BS-1001").json()["order"]["Customer Name"] == "Fatima Al Marri")

    payments = client.get("/api/payments").json()
    check("empty Payments tab falls back to Master Orders",
          payments["source"] == "master_orders" and len(payments["payments"]) == 2)

    # ── Session tampering and expiry ──────────────────────────────────────────
    tampered = fresh_client(FakeSheets())
    signed_in(tampered)
    token = tampered.cookies.get(web_auth.COOKIE_NAME)
    tampered.cookies.set(web_auth.COOKIE_NAME, token[:-1] + ("0" if token[-1] != "0" else "1"))
    check("tampered cookie is refused", tampered.get("/api/orders").status_code == 401)

    expired = web_auth.issue_token("test-session-secret", now=time.time() - web_auth.SESSION_SECONDS - 60)
    check("expired token is refused", not web_auth.token_is_valid(expired, "test-session-secret"))
    check("valid token is accepted",
          web_auth.token_is_valid(web_auth.issue_token("test-session-secret"), "test-session-secret"))
    check("token signed with another secret is refused",
          not web_auth.token_is_valid(web_auth.issue_token("other"), "test-session-secret"))

    # ── Fail closed without configuration ────────────────────────────────────
    saved_password = os.environ.pop("APP_PASSWORD")
    check("login refused when APP_PASSWORD is unset",
          fresh_client(FakeSheets()).post("/api/login", json={"password": ""}).status_code == 503)
    os.environ["APP_PASSWORD"] = saved_password
    check("empty password never matches", not web_auth.password_matches("", ""))

    # ── Payment saves ─────────────────────────────────────────────────────────
    fake = FakeSheets()
    client = signed_in(fresh_client(fake))

    res = client.post("/api/payments/BS-1001", json={"status": "Paid Online", "cod_expected": "99"})
    check("Paid Online saves", res.status_code == 200, res.text)
    master = dict(fake.master_writes[-1][1]) if fake.master_writes else {}
    check("Paid Online forces COD expected to 0 on Master Orders", master.get("COD Expected") == "0", str(master))
    check("Paid Online sets Order Status", master.get("Order Status") == "Paid Online", str(master))

    res = client.post("/api/payments/BS-1001", json={"status": "COD Confirmed", "cod_expected": ""})
    check("COD Confirmed without amount is 400", res.status_code == 400, res.text)
    check("rejected save writes nothing", len(fake.master_writes) == 1 and len(fake.payment_writes) == 1)

    res = client.post("/api/payments/BS-1001", json={"status": "Shipped"})
    check("unknown payment status is 400", res.status_code == 400)

    fake.master_ok = False
    res = client.post("/api/payments/BS-1001", json={"status": "Payment Link Sent"})
    check("failed Master Orders write is 404", res.status_code == 404, res.text)
    check("no Payments write after a failed Master write", len(fake.payment_writes) == 1)
    fake.master_ok = True

    fake.payment_ok = False
    res = client.post("/api/payments/BS-1001", json={"status": "Payment Link Sent"})
    check("missing Payments row is reported, not hidden",
          res.status_code == 200 and res.json()["payments_tab_updated"] is False, res.text)

    fake.fail_reads = True
    res = client.get("/api/orders")
    check("sheet failure is 503", res.status_code == 503, str(res.status_code))
    check("sheet failure does not leak the error text", "credential detail" not in res.text, res.text)

    # ── Pure payment rules ────────────────────────────────────────────────────
    payments_u, master_u = build_payment_updates("Payment Link Sent", "", "https://pay", "", "", "")
    check("Payment Link Sent moves order status", master_u == {"Payment Status": "Payment Link Sent",
                                                               "Order Status": "Payment Link Sent"}, str(master_u))
    check("Payments tab receives the link", payments_u["Payment Link"] == "https://pay")
    try:
        build_payment_updates("COD Confirmed", "", "", "  ", "", "")
        check("blank COD expected is rejected", False, "no error raised")
    except PaymentRuleError:
        check("blank COD expected is rejected", True)

    for name in ("api/index.py", "ops/payments.py", "ops/web_auth.py"):
        check(f"{name} exists", (ROOT / name).exists())

    print(f"WEB API TESTS: {len(PASSES)} passed, {len(FAILURES)} failed")
    for f in FAILURES:
        print("  FAIL", f)
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    sys.exit(run())
