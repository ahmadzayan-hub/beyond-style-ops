"""pages/4_Labels.py — Shipment Labels"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import streamlit as st
import pandas as pd
from ops.config import GOLD, BLACK, LIGHT, STATUS_COLOR
from ops.sheets import get_master_orders, update_master_order

st.set_page_config(page_title="Labels · Beyond Style", page_icon="🏷️", layout="wide")
st.markdown(f"<style>html,body,[class*='css']{{font-family:'Inter',sans-serif;background:{LIGHT}}}</style>",
            unsafe_allow_html=True)

role = st.session_state.get("role", "Read Only")
can_edit = role in ["Owner / Admin", "Packing / Sharon"]

st.title("🏷️ Shipment Labels")

@st.cache_data(ttl=60)
def load():
    df = get_master_orders()
    if df.empty:
        return df
    label_stages = [
        "Customer Approved", "Packed", "Shipment Label Ready",
        "Courier Booked", "Handed to Courier",
    ]
    return df[df["Order Status"].isin(label_stages)].copy() if "Order Status" in df.columns else df

with st.spinner("Loading..."):
    df = load()

if df.empty:
    st.info("No orders ready for label generation.")
    st.stop()

# ── Search/filter ─────────────────────────────────────────────────────────────
fc1, fc2 = st.columns([3, 1])
search    = fc1.text_input("Search Order ID or Customer", "")
ready_only = fc2.checkbox("Label Ready only", value=True)

filtered = df.copy()
if search:
    mask = (
        filtered.get("Order ID", pd.Series()).astype(str).str.contains(search, case=False, na=False) |
        filtered.get("Customer Name", pd.Series()).astype(str).str.contains(search, case=False, na=False)
    )
    filtered = filtered[mask]
if ready_only and "Shipment Label Status" in filtered.columns:
    filtered = filtered[filtered["Shipment Label Status"] == "Ready to Print"]

st.caption(f"**{len(filtered)}** orders")

show_cols = [c for c in [
    "Order ID", "Customer Name", "Mobile Number", "Emirate", "Area",
    "Full Address", "Payment Method", "COD Expected",
    "Product Summary", "Colour / Design", "Quantity",
    "Order Status", "Shipment Label Status",
] if c in filtered.columns]

st.dataframe(filtered[show_cols].reset_index(drop=True), use_container_width=True, height=240)

# ── Label generator ───────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Generate Shipment Label")

order_ids = filtered["Order ID"].dropna().astype(str).tolist()
if not order_ids:
    st.info("No orders in this filter.")
    st.stop()

sel_id = st.selectbox("Select Order ID", order_ids)
order = filtered[filtered["Order ID"].astype(str) == sel_id]
if order.empty:
    st.stop()
o = order.iloc[0].to_dict()

# Build label text
cod_amount = o.get("COD Expected", "")
if str(o.get("Payment Method","")).lower() in ["paid online", "bank transfer", "card", "debit card"]:
    cod_line = "COD AMOUNT: N/A (Prepaid)"
else:
    cod_line = f"COD AMOUNT: AED {cod_amount}" if cod_amount else "COD AMOUNT: TBC"

label_text = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        ✦ BEYOND STYLE UAE ✦
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ORDER ID:        {o.get('Order ID','')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CUSTOMER:        {o.get('Customer Name','')}
MOBILE:          {o.get('Mobile Number','')}
WHATSAPP:        {o.get('WhatsApp Number','')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FULL ADDRESS:    {o.get('Full Address','')}
AREA:            {o.get('Area','')}
EMIRATE:         {o.get('Emirate','')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GOOGLE MAPS:     {o.get('Google Maps Location','')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ITEM:            {o.get('Product Summary','')}
COLOUR / DESIGN: {o.get('Colour / Design','')}
QTY:             {o.get('Quantity','')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PAYMENT STATUS:  {o.get('Payment Status','')}
{cod_line}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DELIVERY SLOT:   {o.get('Preferred Delivery Time','')}
RECEIVER NAME:   {o.get('Receiver Name','')}
STAFF NO:        {o.get('Staff Number','')}
RECEIVED DATE:   {o.get('Actual Received Date','')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SENDER: Beyond Style UAE
TEL: +971 55 155 6991
WEB: www.beyondstyle.ae
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

# Display label
st.markdown(f"""
<div style="background:#fff;border:2px solid {BLACK};border-radius:10px;
            padding:20px 24px;font-family:monospace;font-size:13px;
            white-space:pre;line-height:1.6;max-width:520px;
            box-shadow:0 2px 8px rgba(0,0,0,0.1)">
{label_text}
</div>
""", unsafe_allow_html=True)

# Copy button (via st.code for easy selection)
with st.expander("📋 Copy Label Text"):
    st.code(label_text, language=None)

# ── Mark label ready ──────────────────────────────────────────────────────────
st.markdown("---")
col1, col2 = st.columns(2)

if can_edit:
    qc_status = str(o.get("Packing QC Status",""))
    if col1.button("✅ Mark Label Ready to Print", type="primary"):
        if qc_status not in ["Customer Approved", "Passed"]:
            st.error("❌ QC must be Customer Approved or Passed first.")
        else:
            ok = update_master_order(sel_id, {
                "Shipment Label Status": "Ready to Print",
                "Order Status":          "Shipment Label Ready",
            })
            if ok:
                st.success("✅ Label marked Ready to Print.")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("Update failed.")

    if col2.button("🚚 Mark Courier Booked"):
        ok = update_master_order(sel_id, {
            "Courier Status": "Booked",
            "Order Status":   "Courier Booked",
        })
        if ok:
            st.success("✅ Courier booked.")
            st.cache_data.clear()
            st.rerun()
        else:
            st.error("Update failed.")
else:
    st.caption("🔒 Owner / Admin or Packing / Sharon role required to update labels.")
