"""pages/3_Packing_QC.py — Packing QC"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import streamlit as st
import pandas as pd
from ops.config import QC_STATUSES, GOLD, BLACK, LIGHT, STATUS_COLOR, status_badge
from ops.sheets import get_master_orders, update_master_order

st.set_page_config(page_title="Packing QC · Beyond Style", page_icon="📦", layout="wide")
st.markdown(f"<style>html,body,[class*='css']{{font-family:'Inter',sans-serif;background:{LIGHT}}}</style>",
            unsafe_allow_html=True)

role = st.session_state.get("role", "Read Only")
can_edit = role in ["Owner / Admin", "Packing / Sharon"]

st.title("📦 Packing QC")

@st.cache_data(ttl=60)
def load():
    df = get_master_orders()
    if df.empty:
        return df
    # QC is available from the moment an order is received — no payment gate.
    # COD customers pay on delivery; online customers may approve the product photo before paying.
    exclude = ["Closed Successfully", "Cancelled", "Issue / Return"]
    if "Order Status" in df.columns:
        return df[~df["Order Status"].isin(exclude)].copy()
    return df

with st.spinner("Loading..."):
    df = load()

if df.empty:
    st.info("No orders ready for QC yet.")
    st.stop()

# ── Filters ───────────────────────────────────────────────────────────────────
fc1, fc2 = st.columns([2, 2])
search   = fc1.text_input("Search (Order ID / Customer)", "")
qc_fil   = fc2.selectbox("QC Status", ["All"] + QC_STATUSES)

filtered = df.copy()
if search:
    mask = (
        filtered.get("Customer Name", pd.Series()).astype(str).str.contains(search, case=False, na=False) |
        filtered.get("Order ID", pd.Series()).astype(str).str.contains(search, case=False, na=False)
    )
    filtered = filtered[mask]
if qc_fil != "All" and "Packing QC Status" in filtered.columns:
    filtered = filtered[filtered["Packing QC Status"] == qc_fil]

# ── QC counter cards ──────────────────────────────────────────────────────────
qc_counts = filtered["Packing QC Status"].value_counts() if "Packing QC Status" in filtered.columns else {}
c_cols = st.columns(len(QC_STATUSES))
qc_colors = {
    "Pending": "#E65100", "Product Photo Required": "#F57F17",
    "Photo Sent to Customer": "#0277BD", "Customer Approved": "#2E7D32",
    "Passed": "#1B5E20", "Failed": "#B71C1C", "Rework Required": "#880E4F",
}
for col, qs in zip(c_cols, QC_STATUSES):
    n = qc_counts.get(qs, 0)
    c = qc_colors.get(qs, "#888")
    col.markdown(
        f'<div style="background:#fff;border-top:3px solid {c};border-radius:8px;'
        f'padding:10px 12px;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,0.07)">'
        f'<div style="font-size:22px;font-weight:700;color:{BLACK}">{n}</div>'
        f'<div style="font-size:10px;color:#666">{qs}</div>'
        f'</div>', unsafe_allow_html=True)

st.markdown("---")

# ── QC table ──────────────────────────────────────────────────────────────────
show_cols = [c for c in [
    "Order ID", "Order Date", "Customer Name", "Product Summary",
    "Colour / Design", "Quantity", "Payment Status",
    "Packing QC Status", "Order Status", "Dispatch Gate Status",
] if c in filtered.columns]
st.dataframe(filtered[show_cols].reset_index(drop=True), width='stretch', height=280)

# ── QC update form ────────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Update QC Status")

if not can_edit:
    st.caption("🔒 Packing / Sharon or Owner / Admin role required.")
    st.stop()

order_ids = filtered["Order ID"].dropna().astype(str).tolist()
if not order_ids:
    st.stop()

sel_id = st.selectbox("Select Order ID", order_ids)
order_row = filtered[filtered["Order ID"].astype(str) == sel_id]
if order_row.empty:
    st.stop()
order_row = order_row.iloc[0].to_dict()

st.markdown(f"""
**{order_row.get('Customer Name','')}** · {order_row.get('Product Summary','')} ·
Colour: {order_row.get('Colour / Design','')} · Qty: {order_row.get('Quantity','')}
""")

col_a, col_b = st.columns(2)
with col_a:
    current_qc = str(order_row.get("Packing QC Status", "Pending"))
    new_qc = st.selectbox("Packing QC Status", QC_STATUSES,
                          index=QC_STATUSES.index(current_qc) if current_qc in QC_STATUSES else 0)
    prepared_by   = st.text_input("Prepared By", str(order_row.get("Staff Number", "")))
    prepared_date = st.date_input("Prepared Date")

with col_b:
    qc_notes = st.text_area("QC Notes", str(order_row.get("Phase 3 Notes", "")), height=100)
    photo_link = st.text_input("Product / Packing Photo Link (Drive URL)",
                               str(order_row.get("Proof of Delivery", "")))

st.markdown("##### Quick Actions")
qa1, qa2, qa3, qa4 = st.columns(4)

def _qc_action(label, updates, col):
    if col.button(label, key=f"qca_{label}_{sel_id}"):
        ok = update_master_order(sel_id, updates)
        if ok:
            st.success(f"✅ {label}")
            st.cache_data.clear()
            st.rerun()
        else:
            st.error("Update failed.")

_qc_action("📸 Photo Sent",
    {"Packing QC Status":"Photo Sent to Customer","Order Status":"Product Photo Sent"}, qa1)
_qc_action("✅ Customer Approved",
    {"Packing QC Status":"Customer Approved","Order Status":"Customer Approved",
     "Dispatch Gate Status":"Open"}, qa2)
_qc_action("✔️ Mark Passed",
    {"Packing QC Status":"Passed"}, qa3)
_qc_action("❌ Failed / Rework",
    {"Packing QC Status":"Rework Required","Dispatch Gate Status":"Blocked"}, qa4)

if st.button("💾 Save QC Update", type="primary"):
    updates = {
        "Packing QC Status": new_qc,
        "Internal Notes":    qc_notes,
    }
    if new_qc in ["Customer Approved", "Passed"]:
        updates["Order Status"]        = "Customer Approved" if new_qc == "Customer Approved" else "Packed"
        updates["Dispatch Gate Status"] = "Open"
    elif new_qc in ["Failed", "Rework Required"]:
        updates["Dispatch Gate Status"] = "Blocked"

    ok = update_master_order(sel_id, updates)
    if ok:
        st.success("✅ QC updated.")
        st.cache_data.clear()
        st.rerun()
    else:
        st.error("❌ Update failed.")
