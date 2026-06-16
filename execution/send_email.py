"""
send_email.py  -  Layer 3 (Execution)

Sends the order verification report to the Beyond Style operations inbox.
Uses SMTP (works with Gmail, Google Workspace, Outlook, or any SMTP provider).

Required .env keys:
    SMTP_HOST      e.g. smtp.gmail.com
    SMTP_PORT      587  (TLS) or 465 (SSL)
    SMTP_USERNAME  your sending email address
    SMTP_PASSWORD  app password (Gmail) or account password
    ALERT_EMAIL    destination address, defaults to info@beyondstyle.ae

Gmail / Google Workspace setup (one-time):
    1. Enable 2-Step Verification on the sending account
    2. myaccount.google.com -> Security -> App Passwords
    3. Generate a password for "Mail" / "Windows Computer"
    4. Paste it into SMTP_PASSWORD in .env
"""

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_HOST     = os.getenv("SMTP_HOST", "")
_PORT     = int(os.getenv("SMTP_PORT", "587"))
_USER     = os.getenv("SMTP_USERNAME", "")
_PASS     = os.getenv("SMTP_PASSWORD", "")
_TO       = os.getenv("ALERT_EMAIL", "info@beyondstyle.ae")
_LIVE     = bool(_HOST and _USER and _PASS)


# ── Status colour mapping ─────────────────────────────────────────────────────
_STATUS_COLOUR = {
    "Verified":              "#27ae60",
    "Awaiting Confirmation": "#f39c12",
    "Needs Correction":      "#e67e22",
    "High Risk":             "#c0392b",
    "Do Not Pack":           "#7b241c",
}

_RISK_COLOUR = {
    "Low":      "#27ae60",
    "Medium":   "#f39c12",
    "High":     "#c0392b",
    "Critical": "#7b241c",
}


def _build_subject(order: dict, result: dict) -> str:
    status   = result.get("operational_status", "Unknown")
    name     = order.get("customer_name", "Unknown Customer")
    order_id = order.get("order_id", "")
    prefix   = f"[{order_id}] " if order_id else ""
    return f"[Beyond Style] {prefix}{name} — {status}"


def _build_plain(order: dict, result: dict) -> str:
    lines = [
        "=" * 60,
        "BEYOND STYLE UAE — ORDER VERIFICATION REPORT",
        "=" * 60,
        "",
        f"Customer:   {order.get('customer_name', '')}",
        f"Phone:      {order.get('phone', '')}",
        f"Emirate:    {order.get('emirate', '')}  |  Area: {order.get('area', '')}",
        f"Product:    {order.get('product', '')}  ({order.get('colour', '')})  x{order.get('quantity', '')}",
        f"Total:      AED {order.get('total', '')}  |  Payment: {order.get('payment_method', '')} — {order.get('payment_status', '')}",
        "",
        f"STATUS:     {result.get('operational_status', '')}",
        f"RISK LEVEL: {result.get('risk_level', '')}",
        f"ESCALATION: {'YES — see issues below' if result.get('escalation') else 'No'}",
        "",
    ]

    issues = result.get("missing_or_risky", [])
    if issues:
        lines.append("ISSUES FOUND:")
        for i, issue in enumerate(issues, 1):
            lines.append(f"  {i}. {issue}")
        lines.append("")

    lines.append("NEXT ACTION:")
    lines.append(f"  {result.get('next_action', '')}")
    lines.append("")

    msg = result.get("customer_message", "")
    if msg:
        lines += [
            "-" * 60,
            "DRAFT CUSTOMER MESSAGE:",
            "-" * 60,
            msg,
            "",
        ]

    tracker = result.get("tracker_update", "")
    if tracker:
        lines += [
            "-" * 60,
            "TRACKER UPDATE:",
            "-" * 60,
        ]
        if isinstance(tracker, dict):
            for k, v in tracker.items():
                if v:
                    lines.append(f"  {k}: {v}")
        else:
            lines.append(f"  {tracker}")
        lines.append("")

    lines += [
        "=" * 60,
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "Beyond Style UAE Verification Agent",
        "=" * 60,
    ]
    return "\n".join(lines)


def _build_html(order: dict, result: dict) -> str:
    status     = result.get("operational_status", "")
    risk       = result.get("risk_level", "")
    escalation = result.get("escalation", False)
    issues     = result.get("missing_or_risky", [])
    next_act   = result.get("next_action", "")
    msg        = result.get("customer_message", "")
    generated  = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    s_colour = _STATUS_COLOUR.get(status, "#555")
    r_colour = _RISK_COLOUR.get(risk, "#555")

    issues_html = ""
    if issues:
        items = "".join(f"<li>{i}</li>" for i in issues)
        issues_html = f"""
        <h3 style="color:#c0392b;margin-top:20px;">Issues Found</h3>
        <ul style="margin:0;padding-left:20px;line-height:1.8">{items}</ul>"""

    msg_html = ""
    if msg:
        msg_safe = msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        msg_html = f"""
        <h3 style="margin-top:24px;">Draft Customer Message</h3>
        <div style="background:#f8f9fa;border-left:4px solid #3498db;padding:12px 16px;
                    font-family:monospace;font-size:13px;white-space:pre-wrap;line-height:1.6">
            {msg_safe}
        </div>"""

    escalation_badge = (
        '<span style="background:#c0392b;color:#fff;padding:2px 8px;border-radius:3px;font-size:12px">YES</span>'
        if escalation else
        '<span style="color:#888;font-size:12px">No</span>'
    )

    return f"""<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;max-width:680px;margin:0 auto;padding:20px;color:#333">

  <div style="background:#1a1a2e;padding:16px 24px;border-radius:8px 8px 0 0">
    <h1 style="color:#fff;margin:0;font-size:20px">Beyond Style UAE</h1>
    <p style="color:#aaa;margin:4px 0 0;font-size:13px">Order Verification Report</p>
  </div>

  <div style="border:1px solid #ddd;border-top:none;border-radius:0 0 8px 8px;padding:24px">

    <!-- Status banner -->
    <div style="background:{s_colour};color:#fff;padding:12px 16px;border-radius:6px;
                display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
      <span style="font-size:18px;font-weight:bold">{status}</span>
      <span style="font-size:13px">Risk:
        <strong style="background:{r_colour};padding:2px 8px;border-radius:3px">{risk}</strong>
        &nbsp; Escalation: {escalation_badge}
      </span>
    </div>

    <!-- Order summary -->
    <h3 style="margin:0 0 10px;border-bottom:1px solid #eee;padding-bottom:6px">Order Details</h3>
    <table style="width:100%;border-collapse:collapse;font-size:14px">
      <tr><td style="padding:4px 0;color:#666;width:130px">Customer</td>
          <td style="padding:4px 0"><strong>{order.get("customer_name","")}</strong></td></tr>
      <tr><td style="padding:4px 0;color:#666">Phone</td>
          <td style="padding:4px 0">{order.get("phone","")}</td></tr>
      <tr><td style="padding:4px 0;color:#666">Location</td>
          <td style="padding:4px 0">{order.get("emirate","")}, {order.get("area","")}</td></tr>
      <tr><td style="padding:4px 0;color:#666">Product</td>
          <td style="padding:4px 0">{order.get("product","")} — {order.get("colour","")} × {order.get("quantity","")}</td></tr>
      <tr><td style="padding:4px 0;color:#666">Total</td>
          <td style="padding:4px 0"><strong>AED {order.get("total","")}</strong>
              &nbsp;|&nbsp; {order.get("payment_method","")} — {order.get("payment_status","")}</td></tr>
    </table>

    {issues_html}

    <!-- Next action -->
    <div style="background:#eaf4fb;border-left:4px solid #2980b9;padding:10px 14px;
                margin-top:20px;border-radius:0 4px 4px 0">
      <strong>Next Action:</strong> {next_act}
    </div>

    {msg_html}

    <p style="margin-top:28px;font-size:11px;color:#aaa;border-top:1px solid #eee;padding-top:12px">
      Generated {generated} · Beyond Style UAE Verification Agent
    </p>
  </div>
</body>
</html>"""


def send_verification_email(order: dict, result: dict) -> dict:
    """
    Send the verification report email.

    Returns:
        sent:      bool
        dry_run:   bool
        recipient: str
        error:     str
        timestamp: str
    """
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    if not _LIVE:
        subject = _build_subject(order, result)
        plain   = _build_plain(order, result)
        print(f"[DRY RUN] EMAIL to {_TO}")
        print(f"Subject: {subject}")
        print(plain[:500] + ("..." if len(plain) > 500 else ""))
        return {"sent": True, "dry_run": True, "recipient": _TO,
                "error": "", "timestamp": ts}

    try:
        subject = _build_subject(order, result)
        plain   = _build_plain(order, result)
        html    = _build_html(order, result)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = _USER
        msg["To"]      = _TO
        msg.attach(MIMEText(plain, "plain", "utf-8"))
        msg.attach(MIMEText(html,  "html",  "utf-8"))

        context = ssl.create_default_context()
        if _PORT == 465:
            with smtplib.SMTP_SSL(_HOST, _PORT, context=context) as server:
                server.login(_USER, _PASS)
                server.sendmail(_USER, _TO, msg.as_string())
        else:
            with smtplib.SMTP(_HOST, _PORT) as server:
                server.ehlo()
                server.starttls(context=context)
                server.login(_USER, _PASS)
                server.sendmail(_USER, _TO, msg.as_string())

        return {"sent": True, "dry_run": False, "recipient": _TO,
                "error": "", "timestamp": ts}

    except Exception as e:
        return {"sent": False, "dry_run": False, "recipient": _TO,
                "error": str(e), "timestamp": ts}


if __name__ == "__main__":
    # Quick smoke test with a dummy order
    order = {
        "customer_name":  "Fatima Al Zahra",
        "phone":          "0551234567",
        "emirate":        "Dubai",
        "area":           "Jumeirah",
        "address":        "Villa 5, Street 12",
        "product":        "Hob Necklace",
        "colour":         "Gold",
        "quantity":       1,
        "unit_price":     59,
        "delivery_fee":   25,
        "total":          84,
        "payment_method": "Cash on Delivery",
        "payment_status": "Confirmed",
    }

    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from validate_order import validate_order
    result = validate_order(order)

    r = send_verification_email(order, result)
    print("Sent:", r["sent"])
    print("Dry run:", r["dry_run"])
    print("Recipient:", r["recipient"])
    if r["error"]:
        print("Error:", r["error"])
