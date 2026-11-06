"""
test_access_and_delivery.py  -  server-side role checks and honest message states.

Covers two review findings:
1. A role picked in the sidebar must not grant its own permissions.
2. A dry run must never be recorded as a sent message.

No credentials or network needed. Run:  python tests/test_access_and_delivery.py
"""

import ast
import importlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "execution"))

# Guarantee dry-run mode: no provider credentials in this process.
for var in ("WHATSAPP_API_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "DRY_RUN"):
    os.environ.pop(var, None)

from ops import role_auth  # noqa: E402
import delivery_status  # noqa: E402

PASSES, FAILURES = [], []


def check(name, ok, detail=""):
    (PASSES if ok else FAILURES).append(name if ok else f"{name}: {detail}")


def run() -> int:
    # ── Roles: verified on the server, fail closed ────────────────────────────
    env = {"OPS_PASSCODE_OWNER": "owner-pass-1", "OPS_PASSCODE_PACKING": "pack-pass-2"}
    check("owner with right passcode", role_auth.verify_role("Owner / Admin", "owner-pass-1", env))
    check("owner with wrong passcode", not role_auth.verify_role("Owner / Admin", "owner-pass-X", env))
    check("another role's passcode does not open owner", not role_auth.verify_role("Owner / Admin", "pack-pass-2", env))
    check("role without a configured passcode is closed", not role_auth.verify_role("Sales / WhatsApp", "", env))
    check("empty passcode never matches", not role_auth.verify_role("Owner / Admin", "", {"OPS_PASSCODE_OWNER": ""}))
    check("unknown role refused", not role_auth.verify_role("Superuser", "owner-pass-1", env))
    check("only configured roles offered", role_auth.configured_roles(env) == ["Owner / Admin", "Packing / Sharon"],
          str(role_auth.configured_roles(env)))
    check("nothing configured means no roles", role_auth.configured_roles({}) == [])
    check("dev unlock is explicit", role_auth.configured_roles({"OPS_DEV_UNLOCKED": "1"}) == list(role_auth.ROLE_ENV))
    check("dev unlock needs exactly 1", not role_auth.dev_unlocked({"OPS_DEV_UNLOCKED": "true"}))

    # A self-selected role in session state grants nothing.
    check("legacy 'role' key is ignored", role_auth.verified_role({"role": "Owner / Admin"}) is None)
    check("proved role is returned", role_auth.verified_role({"auth_role": "Packing / Sharon"}) == "Packing / Sharon")
    check("forged unknown role is ignored", role_auth.verified_role({"auth_role": "Superuser"}) is None)

    # Throttle: five failures lock the session for a minute.
    state = {}
    for _ in range(role_auth.MAX_ATTEMPTS):
        check("attempt allowed before lockout", role_auth.attempt_allowed(state, now=1000))
        role_auth.record_attempt(state, False, now=1000)
    check("locked after max failures", not role_auth.attempt_allowed(state, now=1001))
    check("unlocked after the wait", role_auth.attempt_allowed(state, now=1000 + role_auth.LOCKOUT_SECONDS))

    # Every page and the dashboard call require_role() before loading data,
    # and none reads the old self-selected session role.
    for name in ["ops_app.py"] + sorted(str(p.relative_to(ROOT)) for p in (ROOT / "pages").glob("*.py")):
        src = (ROOT / name).read_text(encoding="utf-8")
        check(f"{name} calls require_role()", "require_role()" in src)
        check(f"{name} does not trust session 'role'", 'st.session_state.get("role"' not in src)
        tree = ast.parse(src)
        gate_line = min((n.lineno for n in ast.walk(tree)
                         if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "require_role"), default=None)
        data_lines = [n.lineno for n in ast.walk(tree)
                      if isinstance(n, ast.Call) and getattr(n.func, "id", "").startswith(("get_", "load"))]
        check(f"{name} gates before loading data", gate_line is not None and all(gate_line < l for l in data_lines),
              f"gate={gate_line} data={data_lines[:3]}")

    # ── Delivery: a dry run is never "sent" ───────────────────────────────────
    wa = importlib.import_module("send_whatsapp_message")
    r = wa.send_whatsapp_message("971501234567", "hello")
    check("whatsapp dry run is simulated", r["status"] == delivery_status.SIMULATED, str(r))
    check("whatsapp dry run is not sent", r["sent"] is False, str(r))
    bad = wa.send_whatsapp_message("05x", "hello")
    check("invalid phone is invalid, not sent", bad["status"] == delivery_status.INVALID and not bad["sent"], str(bad))

    em = importlib.import_module("send_email")
    e = em.send_verification_email({"customer_name": "Test", "order_id": "T-1"}, {"operational_status": "Verified"})
    check("email dry run is simulated", e["status"] == delivery_status.SIMULATED and e["sent"] is False, str(e))

    # DRY_RUN forces simulation even with credentials present.
    os.environ.update({"WHATSAPP_API_TOKEN": "x", "WHATSAPP_PHONE_NUMBER_ID": "y", "DRY_RUN": "1"})
    wa2 = importlib.reload(wa)
    check("DRY_RUN=1 keeps whatsapp offline", wa2._LIVE is False)
    for var in ("WHATSAPP_API_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "DRY_RUN"):
        os.environ.pop(var)
    importlib.reload(wa)

    # Tracker values: only a provider acceptance is "Yes"; a simulation has no time or id.
    sim = delivery_status.sheet_fields(r)
    check("simulated row says Dry run", sim["sent_label"] == "Dry run", str(sim))
    check("simulated row has no message id", sim["message_id"] == "" and sim["sent_time"] == "", str(sim))
    acc = delivery_status.sheet_fields({"status": "provider_accepted", "sent": True, "message_id": "wamid.1", "timestamp": "t"})
    check("accepted row says Yes with id", acc == {"sent_label": "Yes", "sent_time": "t", "message_id": "wamid.1"}, str(acc))
    check("failed row says No", delivery_status.sheet_fields({"status": "failed", "sent": False})["sent_label"] == "No")
    legacy = delivery_status.sheet_fields({"sent": True, "dry_run": True, "message_id": "DRY_RUN"})
    check("old-style dry-run result is still Dry run", legacy["sent_label"] == "Dry run", str(legacy))

    btu = importlib.import_module("build_tracker_update")
    out = btu.build_tracker_update({"customer_name": "Test"}, {"operational_status": "Verified"}, send_result=r)
    sent_col = btu._load_map()["whatsapp_message_sent"]
    check("tracker update ran", out.get("ok") is True, str(out)[:200])
    check("tracker update writes Dry run for a dry run", out.get("mapping", {}).get(sent_col) == "Dry run",
          str(out.get("mapping", {}).get(sent_col)))

    print(f"ACCESS AND DELIVERY TESTS: {len(PASSES)} passed, {len(FAILURES)} failed")
    for f in FAILURES:
        print("  FAIL", f)
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    sys.exit(run())
