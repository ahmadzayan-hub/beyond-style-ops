"""
delivery_status.py  -  Layer 3 (Execution)

One vocabulary for "what happened to this message", so a simulation is never
recorded as a delivery.

    invalid            input rejected before any attempt
    simulated          dry run: printed locally, nothing left this machine
    provider_accepted  the provider (Meta / SMTP server) accepted the message.
                       This is NOT proof of delivery to the customer's phone.
    failed             a real attempt was made and the provider refused or errored

`sent` is True only for provider_accepted.
"""

import os

INVALID = "invalid"
SIMULATED = "simulated"
PROVIDER_ACCEPTED = "provider_accepted"
FAILED = "failed"

# Values written to the tracker's "WhatsApp Message Sent" column.
SHEET_LABELS = {
    PROVIDER_ACCEPTED: "Yes",
    SIMULATED: "Dry run",
    INVALID: "No",
    FAILED: "No",
}


def force_dry_run() -> bool:
    """DRY_RUN=1/true/yes forces simulation even when credentials exist."""
    return os.getenv("DRY_RUN", "").strip().lower() in {"1", "true", "yes"}


def status_of(send_result: dict) -> str:
    """Status of a send result, including results from before `status` existed."""
    status = send_result.get("status")
    if status:
        return status
    if send_result.get("dry_run"):
        return SIMULATED
    return PROVIDER_ACCEPTED if send_result.get("sent") else FAILED


def sheet_fields(send_result: dict) -> dict:
    """Tracker values for one send result. A simulation gets no time or message id."""
    status = status_of(send_result)
    real = status == PROVIDER_ACCEPTED
    return {
        "sent_label": SHEET_LABELS.get(status, "No"),
        "sent_time": send_result.get("timestamp", "") if real else "",
        "message_id": send_result.get("message_id", "") if real else "",
    }
