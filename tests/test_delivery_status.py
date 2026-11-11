"""
test_delivery_status.py  -  honest message states.

A dry run must never be recorded as a sent message: results carry a status
(invalid | simulated | provider_accepted | failed) and the tracker writes
"Dry run", not "Yes", for a simulation.

No credentials or network needed. Run:  python tests/test_delivery_status.py
"""

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

import delivery_status  # noqa: E402

PASSES, FAILURES = [], []


def check(name, ok, detail=""):
    (PASSES if ok else FAILURES).append(name if ok else f"{name}: {detail}")


def run() -> int:
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

    print(f"DELIVERY STATUS TESTS: {len(PASSES)} passed, {len(FAILURES)} failed")
    for f in FAILURES:
        print("  FAIL", f)
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    sys.exit(run())
