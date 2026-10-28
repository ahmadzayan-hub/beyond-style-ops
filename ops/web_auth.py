"""ops/web_auth.py — Shared-password login and signed session tokens for the web app.

Fails closed: if APP_PASSWORD or SESSION_SECRET is not set, no login succeeds.
Tokens are "<expiry>.<hmac>" and carry no customer data.
"""

import hashlib
import hmac
import os
import time

COOKIE_NAME = "bso_session"
SESSION_SECONDS = 12 * 60 * 60


def configured_password() -> str:
    return os.getenv("APP_PASSWORD", "")


def configured_secret() -> str:
    return os.getenv("SESSION_SECRET", "")


def password_matches(given: str, expected: str) -> bool:
    """Constant-time comparison. An empty expected password never matches."""
    if not expected or not given:
        return False
    return hmac.compare_digest(given.encode("utf-8"), expected.encode("utf-8"))


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def issue_token(secret: str, now: float | None = None) -> str:
    expiry = int((now if now is not None else time.time()) + SESSION_SECONDS)
    payload = str(expiry)
    return f"{payload}.{_sign(payload, secret)}"


def token_is_valid(token: str, secret: str, now: float | None = None) -> bool:
    if not token or not secret:
        return False
    try:
        payload, signature = token.split(".", 1)
        expiry = int(payload)
    except ValueError:
        return False
    if not hmac.compare_digest(signature, _sign(payload, secret)):
        return False
    return expiry > (now if now is not None else time.time())
