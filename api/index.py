"""api/index.py — Vercel entry point for the Beyond Style ops web app (slice 1).

Routes:
  GET  /api/session                 is the caller signed in?
  POST /api/login                   shared-password sign-in (sets a signed cookie)
  POST /api/logout                  clears the cookie
  GET  /api/options                 status lists for dropdowns
  GET  /api/orders                  Master Orders rows
  GET  /api/orders/{order_id}       one order
  GET  /api/payments                Payments rows (falls back to Master Orders)
  POST /api/payments/{order_id}     save a payment update

Every route except /api/session, /api/login and /api/logout needs a valid session cookie.
"""

import logging
import os
import sys
import time

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from fastapi import Depends, FastAPI, HTTPException, Request, Response  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from ops import sheets  # noqa: E402
from ops import web_auth  # noqa: E402
from ops.config import ORDER_STAGES, PAYMENT_STATUSES  # noqa: E402
from ops.payments import PaymentRuleError, build_payment_updates  # noqa: E402

log = logging.getLogger("bso.web")

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

_ORDERS_CACHE_SECONDS = 60
_orders_cache: dict = {"at": 0.0, "rows": None}


@app.middleware("http")
async def no_store(request: Request, call_next):
    """Customer data must never be cached by a browser or proxy."""
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


class LoginBody(BaseModel):
    password: str


class PaymentBody(BaseModel):
    status: str
    payment_reference: str = ""
    payment_link: str = ""
    cod_expected: str = ""
    cod_collected: str = ""
    notes: str = ""


def _signed_in(request: Request) -> bool:
    secret = web_auth.configured_secret()
    return web_auth.token_is_valid(request.cookies.get(web_auth.COOKIE_NAME, ""), secret)


def require_session(request: Request) -> None:
    if not _signed_in(request):
        raise HTTPException(status_code=401, detail="Sign in required.")


def _sheet_call(fn, *args):
    """Run a sheet operation. Failures are logged server-side, never shown to the browser."""
    try:
        return fn(*args)
    except Exception:
        log.exception("sheet operation failed: %s", getattr(fn, "__name__", "unknown"))
        raise HTTPException(status_code=503, detail="The order sheet is unavailable. Try again shortly.")


def _cached_orders() -> list:
    now = time.time()
    if _orders_cache["rows"] is None or now - _orders_cache["at"] > _ORDERS_CACHE_SECONDS:
        df = _sheet_call(sheets.get_master_orders)
        _orders_cache["rows"] = df.fillna("").astype(str).to_dict(orient="records")
        _orders_cache["at"] = now
    return _orders_cache["rows"]


def _clean(record: dict) -> dict:
    return {k: ("" if v is None else str(v)) for k, v in record.items()}


@app.get("/api/session")
def session(request: Request):
    return {"authenticated": _signed_in(request)}


@app.post("/api/login")
def login(body: LoginBody, response: Response):
    expected = web_auth.configured_password()
    secret = web_auth.configured_secret()
    if not expected or not secret:
        raise HTTPException(status_code=503, detail="Sign-in is not configured on the server.")
    if not web_auth.password_matches(body.password, expected):
        raise HTTPException(status_code=401, detail="Incorrect password.")
    response.set_cookie(
        web_auth.COOKIE_NAME,
        web_auth.issue_token(secret),
        max_age=web_auth.SESSION_SECONDS,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )
    return {"authenticated": True}


@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie(web_auth.COOKIE_NAME, path="/", secure=True, samesite="strict")
    return {"authenticated": False}


@app.get("/api/options", dependencies=[Depends(require_session)])
def options():
    return {"order_stages": ORDER_STAGES, "payment_statuses": PAYMENT_STATUSES}


@app.get("/api/orders", dependencies=[Depends(require_session)])
def list_orders():
    return {"orders": _cached_orders()}


@app.get("/api/orders/{order_id}", dependencies=[Depends(require_session)])
def get_order(order_id: str):
    for row in _cached_orders():
        if row.get("Order ID", "").strip() == order_id.strip():
            return {"order": row}
    raise HTTPException(status_code=404, detail="Order not found.")


@app.get("/api/payments", dependencies=[Depends(require_session)])
def list_payments():
    payments = _sheet_call(sheets.get_payments)
    if payments.empty:
        # Same fallback the Streamlit page used: build the view from Master Orders.
        cols = ["Order ID", "Customer Name", "Total Amount", "Payment Method", "Payment Status",
                "Payment Reference", "Payment Link", "COD Expected", "COD Collected", "COD Difference"]
        rows = [{c: r.get(c, "") for c in cols} for r in _cached_orders()]
        return {"source": "master_orders", "payments": rows}
    rows = payments.fillna("").astype(str).to_dict(orient="records")
    return {"source": "payments", "payments": rows}


@app.post("/api/payments/{order_id}", dependencies=[Depends(require_session)])
def save_payment(order_id: str, body: PaymentBody):
    try:
        payments_updates, master_updates = build_payment_updates(
            status=body.status,
            payment_reference=body.payment_reference,
            payment_link=body.payment_link,
            cod_expected=body.cod_expected,
            cod_collected=body.cod_collected,
            notes=body.notes,
        )
    except PaymentRuleError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not _sheet_call(sheets.update_master_order, order_id, dict(master_updates)):
        raise HTTPException(status_code=404, detail="Order not found, or the update did not reach the sheet.")

    # The Payments tab may not hold this order yet. The Master Orders update still stands,
    # and the response says so, matching the old Streamlit behaviour without hiding it.
    payments_saved = bool(_sheet_call(sheets.update_payment, order_id, dict(payments_updates)))
    _orders_cache["rows"] = None
    return {"ok": True, "payments_tab_updated": payments_saved}
