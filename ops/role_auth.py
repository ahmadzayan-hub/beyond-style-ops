"""ops/role_auth.py — Server-side role verification for the operations console.

A role is granted only after its passcode is checked on the server. Choosing a
role in the sidebar grants nothing by itself.

Each role has its own passcode in an environment variable (see ROLE_ENV).
Fails closed: a role whose variable is empty can never be signed in to.

OPS_DEV_UNLOCKED=1 allows any role without a passcode, for local development
only. The console shows a red warning while it is on. Never set it on a host
that can reach live customer data.

Pure functions only, so they can be tested without Streamlit.
"""

import hmac
import os
import time

ROLE_ENV = {
    "Owner / Admin":      "OPS_PASSCODE_OWNER",
    "Sales / WhatsApp":   "OPS_PASSCODE_SALES",
    "Packing / Sharon":   "OPS_PASSCODE_PACKING",
    "Courier / Delivery": "OPS_PASSCODE_COURIER",
    "Read Only":          "OPS_PASSCODE_READONLY",
}

MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 60


def _env(env):
    return os.environ if env is None else env


def dev_unlocked(env=None) -> bool:
    return _env(env).get("OPS_DEV_UNLOCKED", "") == "1"


def configured_roles(env=None) -> list:
    """Roles that can be signed in to: those with a non-empty passcode."""
    e = _env(env)
    if dev_unlocked(e):
        return list(ROLE_ENV)
    return [role for role, var in ROLE_ENV.items() if e.get(var, "")]


def verify_role(role: str, passcode: str, env=None) -> bool:
    """True only if the role exists and the passcode matches (constant time)."""
    e = _env(env)
    if role not in ROLE_ENV:
        return False
    if dev_unlocked(e):
        return True
    expected = e.get(ROLE_ENV[role], "")
    if not expected or not passcode:
        return False
    return hmac.compare_digest(passcode.encode("utf-8"), expected.encode("utf-8"))


def attempt_allowed(state: dict, now: float | None = None) -> bool:
    """Per-session throttle: after MAX_ATTEMPTS failures, wait LOCKOUT_SECONDS."""
    now = time.time() if now is None else now
    return now >= state.get("auth_locked_until", 0)


def record_attempt(state: dict, ok: bool, now: float | None = None) -> None:
    now = time.time() if now is None else now
    if ok:
        state["auth_failures"] = 0
        state["auth_locked_until"] = 0
        return
    state["auth_failures"] = state.get("auth_failures", 0) + 1
    if state["auth_failures"] >= MAX_ATTEMPTS:
        state["auth_locked_until"] = now + LOCKOUT_SECONDS
        state["auth_failures"] = 0


def verified_role(state: dict):
    """The role this session proved, or None. The legacy 'role' key is ignored."""
    role = state.get("auth_role")
    return role if role in ROLE_ENV else None
