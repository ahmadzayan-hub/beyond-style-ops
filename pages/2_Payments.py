"""pages/2_Payments.py — Payment Control"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import streamlit as st
import pandas as pd
from ops.config import PAYMENT_STATUSES, GOLD, BLACK, LIGHT, status_badge
from ops.sheets import get_payments, get_master_orders, update_payment, update_master_order

st.set_page_config(page_title="Payments · Beyond Style", page_icon="💳", layout="wide")
st.markdown(f"<style>html,body,[class*='css']{{font-family:'Inter',sans-serif;background:{LIGHT}}}</style>",
            unsafe_allow_html=True)

role = st.session_state.get("role", "Read Only")
can_edit = role in ["Owner / Admin", "Sales / WhatsApp"]

st.title("💳 Payment Control")

@st.cache_data(ttl=60)
def load():
    return get_payments(), get_master_orders()

with st.spinner("Loading..."):
    pay_df, orders_df = load()

# ── Filters ───────────────────────────────────────────────────────────────────
fc1, fc2, fc3 = st.columns([2, 2, 2])
search   = fc1.text_input("Search (Order ID / Customer)", "")
stat_fil = fc2.selectbox("Payment Status", ["All"] + PAYMENT_STATUSES)
method_fil = fc3.selectbox("Payment Method",
    ["All"] + sorted(orders_df["Payment Method"].dropna().unique().tolist())
    if not orders_df.empty and "Payment Method" in orders_df.columns else ["All"])

# Merge payment data with order data for richer view
if not pay_df.empty:
    show_df = pay_df.copy()
else:
    # Fallback: build from Master Orders
    cols = [c for c in [
        "Order ID", "Customer Name", "Total Amount", "Payment Method",
        "Payment Status", "Payment Reference", "Payment Link",
        "COD Expected", "COD Collected", "COD Difference",
    ] if c in orders_df.columns]
    show_df = orders_df[cols].copy() if not orders_df.empty else pd.DataFrame()

if show_df.empty:
    st.info("No payment records found.")
    st.stop()

if search:
    mask = (
        show_df.get("Order ID", pd.Series()).astype(str).str.contains(search, case=False, na=False) |
        show_df.get("Customer Name", pd.Series()).astype(str).str.contains(search, case=False, na=False)
    )
    show_df = show_df[mask]

if stat_fil != "All" and "Payment Status" in show_df.columns:
    show_df = show_df[show_df["Payment Status"] == stat_fil]

st.caption(f"**{len(show_df)}** records")

# ── Summary counters ──────────────────────────────────────────────────────────
if not show_df.empty and "Payment Status" in show_df.columns:
    c1, c2, c3, c4 = st.columns(4)
    for col, status, color in [
        (c1, "Payment Pending", "#E65100"),
        (c2, "Paid Online",     "#2E7D32"),
        (c3, "COD Confirmed",   "#00695C"),
        (c4, "COD Collected",   "#1B5E20"),
    ]:
        n = len(show_df[show_df["Payment Status"] == status])
        col.markdown(
            f'<div style="background:#fff;border-left:4px solid {color};'
            f'border-radius:8px;padding:14px 16px;box-shadow:0 1px 4px rgba(0,0,0,0.07)">'
            f'<div style="font-size:26px;font-weight:700;color:{BLACK}">{n}</div>'
            f'<div style="font-size:11px;color:#666;text-transform:uppercase">{status}</div>'
            f'</div>', unsafe_allow_html=True
        )

st.markdown("---")

# ── Table ─────────────────────────────────────────────────────────────────────
st.dataframe(show_df.reset_index(drop=True), width='stretch', height=300)

# ── Payment update form ───────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Update Payment")

if not can_edit:
    st.caption("🔒 You need Owner / Admin or Sales / WhatsApp role to update payments.")
    st.stop()

order_ids = show_df["Order ID"].dropna().astype(str).tolist() if "Order ID" in show_df.columns else []
if not order_ids:
    st.stop()

sel_id = st.selectbox("Select Order ID", order_ids)
order_row = show_df[show_df["Order ID"].astype(str) == sel_id]
if order_row.empty:
    st.stop()
order_row = order_row.iloc[0].to_dict()

col_a, col_b = st.columns(2)
with col_a:
    new_status = st.selectbox("Payment Status",
        PAYMENT_STATUSES,
        index=PAYMENT_STATUSES.index(str(order_row.get("Payment Status", PAYMENT_STATUSES[0])))
        if str(order_row.get("Payment Status")) in PAYMENT_STATUSES else 0)
    pay_ref = st.text_input("Payment Reference", str(order_row.get("Payment Reference", "")))
    pay_link = st.text_input("Payment Link", str(order_row.get("Payment Link", "")))

with col_b:
    cod_expected  = st.text_input("COD Expected (AED)", str(order_row.get("COD Expected", "")))
    cod_collected = st.text_input("COD Collected (AED)", str(order_row.get("COD Collected", "")))
    notes = st.text_area("Notes", str(order_row.get("Notes", "")), height=80)

# Validation
if new_status == "Paid Online":
    st.info("ℹ️ COD Expected will be set to 0 (Paid Online rule).")
    cod_expected = "0"
if new_status == "COD Confirmed" and not cod_expected.strip():
    st.warning("⚠️ COD Expected must be filled for COD Confirmed orders.")

if st.button("💾 Save Payment Update", type="primary"):
    updates = {
        "Payment Status":    new_status,
        "Payment Reference": pay_ref,
        "Payment Link":      pay_link,
        "COD Expected":      cod_expected,
        "COD Collected":     cod_collected,
        "Notes":             notes,
    }
    # Also update Master Orders status
    master_updates = {"Payment Status": new_status}
    if new_status == "Paid Online":
        master_updates["COD Expected"] = "0"
        master_updates["Order Status"] = "Paid Online"
    elif new_status == "COD Confirmed":
        master_updates["Order Status"] = "COD Confirmed"
        master_updates["COD Expected"] = cod_expected
    elif new_status == "Payment Link Sent":
        master_updates["Order Status"] = "Payment Link Sent"

    ok1 = update_payment(sel_id, updates) if not pay_df.empty else True
    ok2 = update_master_order(sel_id, master_updates)

    if ok2:
        st.success("✅ Payment updated.")
        st.cache_data.clear()
        st.rerun()
    else:
        st.error("❌ Update failed.")
