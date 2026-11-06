"""
send_whatsapp_message.py  -  Layer 3 (Execution)

Stub for the WhatsApp Business Cloud API.
Logs a dry-run when credentials are not in .env.
Real sending activates automatically when WHATSAPP_API_TOKEN and
WHATSAPP_PHONE_NUMBER_ID are set.

API reference: https://developers.facebook.com/docs/whatsapp/cloud-api/messages
"""

import os
import json
from datetime import datetime

from delivery_status import FAILED, INVALID, PROVIDER_ACCEPTED, SIMULATED, force_dry_run

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_TOKEN          = os.getenv("WHATSAPP_API_TOKEN", "")
_PHONE_ID       = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
_BUSINESS_NUM   = os.getenv("BUSINESS_WHATSAPP_NUMBER", "971551556991")
_API_VER        = "v19.0"
_LIVE           = bool(_TOKEN and _PHONE_ID) and not force_dry_run()


def send_whatsapp_message(to_international: str, message_text: str) -> dict:
    """
    Args:
        to_international: E.164 number, digits only (e.g. 971501234567)
        message_text:     plain text body

    Returns:
        status:     invalid | simulated | provider_accepted | failed
                    (see delivery_status.py; accepted is not proof of delivery)
        sent:       bool  - True only when Meta accepted the message
        message_id: str   - Meta message ID, or "DRY_RUN"
        dry_run:    bool
        error:      str
        timestamp:  str   - UTC ISO-8601
    """
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    if not to_international or not to_international.isdigit():
        return {"status": INVALID, "sent": False, "message_id": "", "dry_run": not _LIVE,
                "error": f"Invalid international phone: '{to_international}'",
                "timestamp": ts}

    if not _LIVE:
        print(f"[DRY RUN] FROM: +{_BUSINESS_NUM}  ->  TO: +{to_international}")
        print(message_text + "\n")
        return {"status": SIMULATED, "sent": False, "message_id": "DRY_RUN", "dry_run": True,
                "error": "", "timestamp": ts}

    try:
        import urllib.request
        url     = f"https://graph.facebook.com/{_API_VER}/{_PHONE_ID}/messages"
        payload = json.dumps({
            "messaging_product": "whatsapp",
            "to":   to_international,
            "type": "text",
            "text": {"body": message_text},
        }).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {_TOKEN}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body   = json.loads(resp.read().decode("utf-8"))
            msg_id = body.get("messages", [{}])[0].get("id", "")
            return {"status": PROVIDER_ACCEPTED, "sent": True, "message_id": msg_id, "dry_run": False,
                    "error": "", "timestamp": ts}
    except Exception as e:
        return {"status": FAILED, "sent": False, "message_id": "", "dry_run": False,
                "error": str(e), "timestamp": ts}
