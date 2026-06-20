"""pages/1_Orders.py — Orders Control"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import streamlit as st
import pandas as pd
from ops.config import (
    ORDER_STAGES, STATUS_COLOR, STAGE_ACTIONS, ROLES,
    GOLD, BLACK, LIGHT, status_badge, risk_badge
)
from ops.sheets import get_master_orders, update_master_order

st.set_page_config(page_title="Orders · Beyond Style", page_icon="📋", layout="wide")

st.markdown(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
  html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; background: {LIGHT}; }}
  .action-btn {{ background:{GOLD};color:{BLACK};border:none;border-radius:8px;
                 padding:10px 20px;font-weight:700;cursor:pointer;margin:4px;font-size:14px; }}
  .order-card {{ background:#fff;border-radius:12px;padding:20px 24px;
                 box-shadow:0 1px 6px rgba(0,0,0,0.08);margin-bottom:16px; }}
  .field-row {{ display:flex;gap:24px;flex-wrap:wrap;margin-top:8px; }}
  .field-item {{ min-width:160px; }}
  .field-label {{ font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.5px; }}
  .field-value {{ font-size:14px;font-weight:500;color:{BLACK};margin-top:2px; }}
</style>
""", unsafe_allow_html=True)

# ── Role ──────────────────────────────────────────────────────────────────────
role = st.session_state.get("role", "Read Only")
can_edit = role in ["Owner / Admin", "Sales / WhatsApp"]

# ── Load ──────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load():
    return get_master_orders()

st.title("📋 Orders Control")

with st.spinner("Loading..."):
    df = load()

if df.empty:
    st.info("No orders found.")
    st.stop()

# ── Filters ───────────────────────────────────────────────────────────────────
with st.expander("🔍 Filter & Search", expanded=True):
    fc1, fc2, fc3, fc4 = st.columns([2, 2, 2, 2])
    search     = fc1.text_input("Search (name / order ID / phone)", "")
    status_fil = fc2.selectbox("Order Status", ["All"] + ORDER_STAGES)
    emirate_fil = fc3.selectbox("Emirate",
        ["All"] + sorted(df["Emirate"].dropna().unique().tolist()) if "Emirate" in df.columns else ["All"])
    risk_fil = fc4.selectbox("Risk Status",
        ["All"] + sorted(df["Risk Status"].dropna().unique().tolist()) if "Risk Status" in df.columns else ["All"])

filtered = df.copy()
if search:
    mask = (
        filtered.get("Customer Name", pd.Series()).astype(str).str.contains(search, case=False, na=False) |
        filtered.get("Order ID",      pd.Series()).astype(str).str.contains(search, case=False, na=False) |
        filtered.get("Mobile Number", pd.Series()).astype(str).str.contains(search, case=False, na=False)
    )
    filtered = filtered[mask]
if status_fil != "All":
    filtered = filtered[filtered["Order Status"] == status_fil]
if emirate_fil != "All" and "Emirate" in filtered.columns:
    filtered = filtered[filtered["Emirate"] == emirate_fil]
if risk_fil != "All" and "Risk Status" in filtered.columns:
    filtered = filtered[filtered["Risk Status"] == risk_fil]

st.caption(f"Showing **{len(filtered)}** of {len(df)} orders")

# ── Table ─────────────────────────────────────────────────────────────────────
display_cols = [c for c in [
    "Order ID", "Order Date", "Customer Name", "Mobile Number",
    "Product Summary", "Colour / Design", "Quantity", "Total Amount",
    "Payment Method", "Payment Status", "Emirate", "Area",
    "Order Status", "Packing QC Status", "Dispatch Gate Status",
    "Shipment Label Status", "Courier Status", "Delivery Status",
    "Risk Status", "Critical Data Status",
] if c in filtered.columns]

display_df = filtered[display_cols].copy().reset_index(drop=True)

def color_status(val):
    c = STATUS_COLOR.get(str(val), "")
    return f"background:{c}20;color:{c};font-weight:600" if c else ""

st.dataframe(
    display_df.style.map(color_status,
        subset=[c for c in ["Order Status", "Payment Status"] if c in display_df.columns]),
    width='stretch',
    height=340,
)

# ── Order detail + actions ────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Order Detail & Actions")

order_ids = filtered["Order ID"].dropna().astype(str).tolist()
if not order_ids:
    st.info("No orders match the current filter.")
    st.stop()

selected_id = st.selectbox("Select Order ID", order_ids,
                            index=order_ids.index(st.session_state.get("selected_order", order_ids[0]))
                            if st.session_state.get("selected_order") in order_ids else 0)
st.session_state["selected_order"] = selected_id

order = filtered[filtered["Order ID"].astype(str) == selected_id].iloc[0].to_dict()
current_status = str(order.get("Order Status", ""))

# Info card
with st.container():
    st.markdown(f"""
    <div class="order-card">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
        <div>
          <span style="font-size:18px;font-weight:700;color:{BLACK}">{order.get("Order ID","")}</span>
          &nbsp;&nbsp;
          {status_badge(current_status)}
          &nbsp;
          {risk_badge(str(order.get("Risk Status","")))}
        </div>
        <div style="font-size:13px;color:#888">{order.get("Order Date","")}</div>
      </div>
      <div class="field-row" style="margin-top:16px">
        <div class="field-item"><div class="field-label">Customer</div>
          <div class="field-value">{order.get("Customer Name","")}</div></div>
        <div class="field-item"><div class="field-label">Mobile</div>
          <div class="field-value">{order.get("Mobile Number","")}</div></div>
        <div class="field-item"><div class="field-label">WhatsApp</div>
          <div class="field-value">{order.get("WhatsApp Number","")}</div></div>
        <div class="field-item"><div class="field-label">Instagram</div>
          <div class="field-value">{order.get("Instagram Username","")}</div></div>
      </div>
      <div class="field-row">
        <div class="field-item"><div class="field-label">Product</div>
          <div class="field-value">{order.get("Product Summary","")}</div></div>
        <div class="field-item"><div class="field-label">Colour</div>
          <div class="field-value">{order.get("Colour / Design","")}</div></div>
        <div class="field-item"><div class="field-label">Qty</div>
          <div class="field-value">{order.get("Quantity","")}</div></div>
        <div class="field-item"><div class="field-label">Total</div>
          <div class="field-value">AED {order.get("Total Amount","")}</div></div>
      </div>
      <div class="field-row">
        <div class="field-item"><div class="field-label">Payment</div>
          <div class="field-value">{order.get("Payment Method","")} · {order.get("Payment Status","")}</div></div>
        <div class="field-item"><div class="field-label">Location</div>
          <div class="field-value">{order.get("Emirate","")}, {order.get("Area","")}</div></div>
        <div class="field-item"><div class="field-label">Address</div>
          <div class="field-value">{order.get("Full Address","")}</div></div>
      </div>
      <div class="field-row">
        <div class="field-item"><div class="field-label">QC Status</div>
          <div class="field-value">{order.get("Packing QC Status","")}</div></div>
        <div class="field-item"><div class="field-label">Dispatch Gate</div>
          <div class="field-value">{order.get("Dispatch Gate Status","")}</div></div>
        <div class="field-item"><div class="field-label">Label Status</div>
          <div class="field-value">{order.get("Shipment Label Status","")}</div></div>
        <div class="field-item"><div class="field-label">Courier</div>
          <div class="field-value">{order.get("Courier Status","")}</div></div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    if order.get("Internal Notes"):
        st.info(f"📝 **Internal Notes:** {order['Internal Notes']}")
    if order.get("Google Maps Location"):
        st.markdown(f"📍 [Open Google Maps]({order['Google Maps Location']})")

# ── Actions ───────────────────────────────────────────────────────────────────
if role == "Read Only":
    st.caption("👁️ Read-only mode — no actions available.")
    st.stop()

available_actions = STAGE_ACTIONS.get(current_status, [])

st.markdown("#### ⚡ Actions")
if not available_actions:
    st.caption("No actions available for current status.")
else:
    acols = st.columns(min(len(available_actions), 4))
    for col, action in zip(acols, available_actions):
        if col.button(action, key=f"act_{action}_{selected_id}"):
            updates = {}

            if action == "Process Order":
                updates = {"Order Status": "Critical Data Check"}

            elif action == "Mark Payment Link Sent":
                updates = {"Payment Status": "Payment Link Sent", "Order Status": "Payment Link Sent"}

            elif action == "Mark Paid Online":
                updates = {"Payment Status": "Paid Online", "COD Expected": "0",
                           "Order Status": "Paid Online"}

            elif action == "Mark COD Confirmed":
                updates = {"Payment Status": "COD Confirmed", "Order Status": "COD Confirmed"}

            elif action == "Send to QC":
                updates = {"Order Status": "QC Pending", "Packing QC Status": "Pending"}

            elif action == "Photo Sent to Customer":
                updates = {"Packing QC Status": "Photo Sent to Customer",
                           "Order Status": "Product Photo Sent"}

            elif action == "Customer Approved":
                updates = {"Packing QC Status": "Customer Approved",
                           "Order Status": "Customer Approved",
                           "Dispatch Gate Status": "Open"}

            elif action == "Mark Packed":
                updates = {"Order Status": "Packed"}

            elif action == "Mark Label Ready":
                qc = str(order.get("Packing QC Status", ""))
                if qc not in ["Customer Approved", "Passed"]:
                    st.error("❌ QC must be Customer Approved or Passed before label can be marked ready.")
                else:
                    updates = {"Shipment Label Status": "Ready to Print",
                               "Order Status": "Shipment Label Ready"}

            elif action == "Courier Booked":
                updates = {"Courier Status": "Booked", "Order Status": "Courier Booked"}

            elif action == "Handed to Courier":
                updates = {"Courier Status": "Handed to Courier",
                           "Order Status": "Handed to Courier"}

            elif action == "Mark Delivered":
                missing = []
                if not str(order.get("Receiver Name","")).strip(): missing.append("Receiver Name")
                if not str(order.get("Staff Number","")).strip(): missing.append("Staff Number")
                if not str(order.get("Actual Received Date","")).strip(): missing.append("Actual Received Date")
                if not str(order.get("Proof of Delivery","")).strip(): missing.append("Proof of Delivery")
                if missing:
                    st.error(f"❌ Cannot mark Delivered. Missing: {', '.join(missing)}")
                else:
                    updates = {"Delivery Status": "Delivered", "Order Status": "Delivered"}

            elif action == "Request Review":
                updates = {"Order Status": "Review Requested"}

            elif action == "Close Successfully":
                ds = str(order.get("Delivery Status",""))
                rn = str(order.get("Receiver Name","")).strip()
                ard = str(order.get("Actual Received Date","")).strip()
                pod = str(order.get("Proof of Delivery","")).strip()
                if ds not in ["Delivered", "POD Received"]:
                    st.error("❌ Delivery Status must be Delivered or POD Received.")
                elif not rn or not ard or not pod:
                    st.error("❌ Receiver Name, Actual Received Date, and Proof of Delivery are required.")
                else:
                    updates = {"Order Status": "Closed Successfully"}

            if updates:
                with st.spinner(f"Updating..."):
                    ok = update_master_order(selected_id, updates)
                if ok:
                    st.success(f"✅ {action} — order updated.")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("❌ Update failed. Check logs.")

# ── Manual field edit (Owner only) ────────────────────────────────────────────
if role == "Owner / Admin":
    with st.expander("✏️ Manual Field Edit (Owner only)", expanded=False):
        edit_fields = {
            "Internal Notes":        str(order.get("Internal Notes", "")),
            "Phase 3 Notes":         str(order.get("Phase 3 Notes", "")),
            "Critical Data Status":  str(order.get("Critical Data Status", "")),
            "Risk Status":           str(order.get("Risk Status", "")),
            "Next Follow-up Date":   str(order.get("Next Follow-up Date", "")),
        }
        updated_vals = {}
        for field, current_val in edit_fields.items():
            updated_vals[field] = st.text_input(field, current_val, key=f"edit_{field}")

        if st.button("💾 Save Manual Edits", key="save_manual"):
            changes = {k: v for k, v in updated_vals.items() if v != edit_fields[k]}
            if changes:
                ok = update_master_order(selected_id, changes)
                if ok:
                    st.success("Saved.")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("Save failed.")
            else:
                st.info("No changes to save.")
