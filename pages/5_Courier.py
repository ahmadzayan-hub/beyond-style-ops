"""pages/5_Courier.py — Courier & Delivery Tracking"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import streamlit as st
import pandas as pd
from ops.config import COURIER_STATUSES, DELIVERY_STATUSES, GOLD, BLACK, LIGHT, status_badge
from ops.sheets import get_master_orders, get_courier_tracking, update_master_order, update_courier

st.set_page_config(page_title="Courier · Beyond Style", page_icon="🚚", layout="wide")
st.markdown(f"<style>html,body,[class*='css']{{font-family:'Inter',sans-serif;background:{LIGHT}}}</style>",
            unsafe_allow_html=True)

role = st.session_state.get("role", "Read Only")
can_edit = role in ["Owner / Admin", "Courier / Delivery"]

st.title("🚚 Courier & Delivery Tracking")

@st.cache_data(ttl=60)
def load():
    orders = get_master_orders()
    courier = get_courier_tracking()
    if not orders.empty:
        active = [
            "Shipment Label Ready","Courier Booked","Handed to Courier",
            "Out for Delivery","Delivered","POD Received",
        ]
        orders = orders[orders["Order Status"].isin(active)].copy() if "Order Status" in orders.columns else orders
    return orders, courier

with st.spinner("Loading..."):
    orders_df, courier_df = load()

if orders_df.empty:
    st.info("No active courier/delivery orders.")
    st.stop()

# ── Summary ───────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
metrics = [
    (c1, "Courier Booked",     "#1565C0"),
    (c2, "Handed to Courier",  "#4527A0"),
    (c3, "Out for Delivery",   "#1976D2"),
    (c4, "Delivered",          "#2E7D32"),
    (c5, "POD Received",       "#00695C"),
]
for col, stage, color in metrics:
    n = len(orders_df[orders_df["Order Status"] == stage]) if "Order Status" in orders_df.columns else 0
    col.markdown(
        f'<div style="background:#fff;border-top:3px solid {color};border-radius:8px;'
        f'padding:10px 12px;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,0.07)">'
        f'<div style="font-size:22px;font-weight:700;color:{BLACK}">{n}</div>'
        f'<div style="font-size:11px;color:#666">{stage}</div>'
        f'</div>', unsafe_allow_html=True)

st.markdown("---")

# ── Filters ───────────────────────────────────────────────────────────────────
fc1, fc2, fc3 = st.columns([2, 2, 2])
search     = fc1.text_input("Search", "")
stat_fil   = fc2.selectbox("Courier Status", ["All"] + COURIER_STATUSES)
deliv_fil  = fc3.selectbox("Delivery Status", ["All"] + DELIVERY_STATUSES)

filtered = orders_df.copy()
if search:
    mask = (
        filtered.get("Order ID", pd.Series()).astype(str).str.contains(search, case=False, na=False) |
        filtered.get("Customer Name", pd.Series()).astype(str).str.contains(search, case=False, na=False)
    )
    filtered = filtered[mask]
if stat_fil != "All" and "Courier Status" in filtered.columns:
    filtered = filtered[filtered["Courier Status"] == stat_fil]
if deliv_fil != "All" and "Delivery Status" in filtered.columns:
    filtered = filtered[filtered["Delivery Status"] == deliv_fil]

show_cols = [c for c in [
    "Order ID", "Order Date", "Customer Name", "Mobile Number",
    "Emirate", "Area", "Full Address", "Google Maps Location",
    "Payment Method", "COD Expected",
    "Product Summary", "Quantity",
    "Courier Company", "AWB / Tracking Number",
    "Courier Status", "Delivery Status",
    "Receiver Name", "Staff Number", "Actual Received Date", "Proof of Delivery",
    "Order Status",
] if c in filtered.columns]

st.dataframe(filtered[show_cols].reset_index(drop=True), use_container_width=True, height=260)

# ── Update form ───────────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Update Courier / Delivery")

if not can_edit:
    st.caption("🔒 Courier / Delivery or Owner / Admin role required.")
    st.stop()

order_ids = filtered["Order ID"].dropna().astype(str).tolist()
if not order_ids:
    st.stop()

sel_id = st.selectbox("Select Order ID", order_ids)
order = filtered[filtered["Order ID"].astype(str) == sel_id]
if order.empty:
    st.stop()
o = order.iloc[0].to_dict()

st.markdown(f"""
**{o.get('Customer Name','')}** · {o.get('Product Summary','')} ·
📍 {o.get('Area','')}, {o.get('Emirate','')}
""")

col_a, col_b = st.columns(2)
with col_a:
    courier_co = st.text_input("Courier Company", str(o.get("Courier Company","")))
    awb = st.text_input("AWB / Tracking Number", str(o.get("AWB / Tracking Number","")))
    curr_cs = str(o.get("Courier Status","Not Booked"))
    new_cs = st.selectbox("Courier Status", COURIER_STATUSES,
                          index=COURIER_STATUSES.index(curr_cs) if curr_cs in COURIER_STATUSES else 0)
    curr_ds = str(o.get("Delivery Status","Pending Dispatch"))
    new_ds = st.selectbox("Delivery Status", DELIVERY_STATUSES,
                          index=DELIVERY_STATUSES.index(curr_ds) if curr_ds in DELIVERY_STATUSES else 0)

with col_b:
    receiver    = st.text_input("Receiver Name *", str(o.get("Receiver Name","")))
    staff_num   = st.text_input("Staff / Courier Number * (or N/A)", str(o.get("Staff Number","")))
    recv_date   = st.text_input("Actual Received Date *", str(o.get("Actual Received Date","")))
    pod         = st.text_area("Proof of Delivery * (description or URL)", str(o.get("Proof of Delivery","")), height=80)
    courier_notes = st.text_input("Courier Notes", "")

st.markdown("##### Quick Actions")
qa1, qa2, qa3 = st.columns(3)

def _quick(label, col, upd):
    if col.button(label, key=f"cq_{label}_{sel_id}"):
        ok = update_master_order(sel_id, upd)
        if ok:
            st.success(f"✅ {label}")
            st.cache_data.clear()
            st.rerun()
        else:
            st.error("Update failed.")

_quick("🚚 Handed to Courier",
    qa1, {"Courier Status":"Handed to Courier","Order Status":"Handed to Courier"})
_quick("📦 Out for Delivery",
    qa2, {"Courier Status":"Out for Delivery","Order Status":"Out for Delivery"})
_quick("📬 POD Received",
    qa3, {"Delivery Status":"POD Received","Order Status":"POD Received"})

if st.button("💾 Save Delivery Update", type="primary"):
    # Validate for delivered closeout
    if new_ds in ["Delivered", "POD Received"]:
        missing = []
        if not receiver.strip(): missing.append("Receiver Name")
        if not staff_num.strip(): missing.append("Staff / Courier Number")
        if not recv_date.strip(): missing.append("Actual Received Date")
        if not pod.strip(): missing.append("Proof of Delivery")
        if missing:
            st.error(f"❌ Cannot mark Delivered. Missing: {', '.join(missing)}")
            st.stop()

    master_updates = {
        "Courier Company":       courier_co,
        "AWB / Tracking Number": awb,
        "Courier Status":        new_cs,
        "Delivery Status":       new_ds,
        "Receiver Name":         receiver,
        "Staff Number":          staff_num,
        "Actual Received Date":  recv_date,
        "Proof of Delivery":     pod,
    }
    if new_ds in ["Delivered", "POD Received"]:
        master_updates["Order Status"] = new_ds

    ok = update_master_order(sel_id, master_updates)
    if ok:
        st.success("✅ Delivery updated.")
        st.cache_data.clear()
        st.rerun()
    else:
        st.error("❌ Update failed.")
