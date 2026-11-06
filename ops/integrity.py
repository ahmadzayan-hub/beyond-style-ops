"""Shared, deterministic order evidence checks for every dashboard write path."""

DELIVERY_EVIDENCE = ("Receiver Name", "Staff Number", "Actual Received Date", "Proof of Delivery")
DELIVERED = {"Delivered", "POD Received"}


class UpdateValidationError(ValueError):
    """A safe explanation containing field names, never order values or credentials."""


def _filled(value):
    # Sheets supplies strings. Reject nulls and common missing-data sentinels too.
    return value is not None and str(value).strip().lower() not in {"", "none", "nan", "<na>"}


def validate_order_update(current, updates):
    """Validate the merged persisted record, never just cached form state.

    These are existing delivery/closeout and label requirements, not a new
    complete lifecycle graph. Staff Number may be N/A, as the courier form allows.
    """
    merged = {**current, **updates}
    order_status = str(merged.get("Order Status", "")).strip()
    delivery_status = str(merged.get("Delivery Status", "")).strip()
    courier_status = str(merged.get("Courier Status", "")).strip()
    if (order_status in DELIVERED | {"Closed Successfully"}
            or delivery_status in DELIVERED or courier_status == "Delivered"):
        missing = [field for field in DELIVERY_EVIDENCE if not _filled(merged.get(field))]
        if missing:
            raise UpdateValidationError("Delivery evidence required: " + ", ".join(missing) + ".")
    if order_status == "Closed Successfully":
        if delivery_status not in DELIVERED:
            raise UpdateValidationError("Delivery Status must be Delivered or POD Received before closeout.")
        if not _filled(merged.get("Customer Satisfaction Score")):
            raise UpdateValidationError("Customer Satisfaction Score is required before closeout.")
    if (updates.get("Order Status") == "Shipment Label Ready"
            or updates.get("Shipment Label Status") == "Ready to Print"):
        if merged.get("Packing QC Status") not in {"Customer Approved", "Passed"}:
            raise UpdateValidationError("QC must be Customer Approved or Passed before the label is ready.")
