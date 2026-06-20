"""ops/config.py — Enums, colors, roles, stage definitions."""

# ── Brand colors ──────────────────────────────────────────────────────────────
GOLD   = "#C9A84C"
BLACK  = "#1A1A1A"
WHITE  = "#FFFFFF"
BEIGE  = "#F5F0E8"
LIGHT  = "#FAFAF8"

# ── Order lifecycle (21 stages) — QC happens BEFORE payment ──────────────────
ORDER_STAGES = [
    "New Form Order",
    "Critical Data Check",
    "QC Pending",
    "Product Photo Sent",
    "Customer Approved",
    "Payment Pending",
    "Payment Link Sent",
    "Paid Online",
    "COD Confirmed",
    "Packed",
    "Shipment Label Ready",
    "Courier Booked",
    "Handed to Courier",
    "Out for Delivery",
    "Delivered",
    "POD Received",
    "Review Requested",
    "Review Received",
    "Closed Successfully",
    "Issue / Return",
    "Cancelled",
]

# ── Status → hex color ────────────────────────────────────────────────────────
STATUS_COLOR = {
    "New Form Order":       "#1565C0",
    "Critical Data Check":  "#6A1B9A",
    "Payment Pending":      "#E65100",
    "Payment Link Sent":    "#0277BD",
    "Paid Online":          "#2E7D32",
    "COD Confirmed":        "#00695C",
    "QC Pending":           "#F9A825",
    "Product Photo Sent":   "#00838F",
    "Customer Approved":    "#558B2F",
    "Packed":               "#388E3C",
    "Shipment Label Ready": "#0288D1",
    "Courier Booked":       "#283593",
    "Handed to Courier":    "#4527A0",
    "Out for Delivery":     "#1976D2",
    "Delivered":            "#2E7D32",
    "POD Received":         "#00695C",
    "Review Requested":     "#F57F17",
    "Review Received":      "#689F38",
    "Closed Successfully":  "#1B5E20",
    "Issue / Return":       "#B71C1C",
    "Cancelled":            "#616161",
}

def status_badge(status: str) -> str:
    color = STATUS_COLOR.get(status, "#888")
    return (
        f'<span style="background:{color};color:#fff;padding:3px 10px;'
        f'border-radius:12px;font-size:12px;font-weight:600;white-space:nowrap">'
        f'{status}</span>'
    )

def risk_badge(risk: str) -> str:
    c = {"Low": "#2E7D32", "Medium": "#E65100", "High": "#B71C1C", "Critical": "#880E4F"}.get(risk, "#888")
    return f'<span style="background:{c};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px">{risk}</span>'

# ── Payment status ────────────────────────────────────────────────────────────
PAYMENT_STATUSES = [
    "Payment Pending",
    "Payment Link Sent",
    "Paid Online",
    "COD Confirmed",
    "COD Collected",
    "Refund Required",
    "Cancelled",
]

# ── Packing QC status ─────────────────────────────────────────────────────────
QC_STATUSES = [
    "Pending",
    "Product Photo Required",
    "Photo Sent to Customer",
    "Customer Approved",
    "Passed",
    "Failed",
    "Rework Required",
]

# ── Courier status ────────────────────────────────────────────────────────────
COURIER_STATUSES = [
    "Not Booked", "Booked", "Handed to Courier",
    "Out for Delivery", "Delivered", "Failed Attempt", "Returned", "Cancelled",
]

DELIVERY_STATUSES = [
    "Pending Dispatch", "Handed to Courier", "Out for Delivery",
    "Delivered", "POD Received", "Failed Delivery", "Returned", "Cancelled",
]

# ── Customer satisfaction ─────────────────────────────────────────────────────
SATISFACTION_SCORES = [
    "5 Very Happy", "4 Happy", "3 Neutral", "2 Not Happy", "1 Complaint",
]

# ── Roles ─────────────────────────────────────────────────────────────────────
ROLES = ["Owner / Admin", "Sales / WhatsApp", "Packing / Sharon", "Courier / Delivery", "Read Only"]

ROLE_COLORS = {
    "Owner / Admin":      GOLD,
    "Sales / WhatsApp":   "#1976D2",
    "Packing / Sharon":   "#388E3C",
    "Courier / Delivery": "#6A1B9A",
    "Read Only":          "#616161",
}

# ── Master Orders — columns shown per role ────────────────────────────────────
ORDERS_DISPLAY_COLS = [
    "Order ID", "Order Date", "Customer Name", "Mobile Number",
    "Product Summary", "Colour / Design", "Quantity", "Total Amount",
    "Payment Method", "Payment Status", "Emirate", "Area",
    "Order Status", "Packing QC Status", "Dispatch Gate Status",
    "Shipment Label Status", "Courier Status", "Delivery Status",
    "Risk Status", "Critical Data Status",
]

# ── Actions available per order status — QC-first flow ───────────────────────
STAGE_ACTIONS = {
    "New Form Order":       ["Process Order", "Send to QC"],
    "Critical Data Check":  ["Send to QC"],
    "QC Pending":           ["Photo Sent to Customer"],
    "Product Photo Sent":   ["Customer Approved"],
    "Customer Approved":    ["Mark Payment Link Sent", "Mark COD Confirmed", "Mark Packed"],
    "Payment Pending":      ["Mark Payment Link Sent", "Mark COD Confirmed"],
    "Payment Link Sent":    ["Mark Paid Online", "Mark COD Confirmed"],
    "Paid Online":          ["Mark Packed"],
    "COD Confirmed":        ["Mark Packed"],
    "Packed":               ["Mark Label Ready"],
    "Shipment Label Ready": ["Courier Booked"],
    "Courier Booked":       ["Handed to Courier"],
    "Handed to Courier":    ["Mark Delivered"],
    "Out for Delivery":     ["Mark Delivered"],
    "Delivered":            ["Request Review"],
    "POD Received":         ["Request Review"],
    "Review Requested":     ["Close Successfully"],
    "Review Received":      ["Close Successfully"],
}
