"""pages/6_Reviews.py — Customer Reviews & Closeout"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import streamlit as st
import pandas as pd
from ops.config import SATISFACTION_SCORES, GOLD, BLACK, LIGHT, STATUS_COLOR, status_badge
from ops.sheets import get_master_orders, update_master_order

st.set_page_config(page_title="Reviews · Beyond Style", page_icon="⭐", layout="wide")
st.markdown(f"<style>html,body,[class*='css']{{font-family:'Inter',sans-serif;background:{LIGHT}}}</style>",
            unsafe_allow_html=True)

role = st.session_state.get("role", "Read Only")
can_edit = role in ["Owner / Admin", "Sales / WhatsApp"]

st.title("⭐ Customer Reviews & Closeout")

@st.cache_data(ttl=60)
def load():
    df = get_master_orders()
    if df.empty:
        return df
    review_stages = [
        "Delivered","POD Received","Review Requested","Review Received","Closed Successfully",
    ]
    return df[df["Order Status"].isin(review_stages)].copy() if "Order Status" in df.columns else df

with st.spinner("Loading..."):
    df = load()

if df.empty:
    st.info("No orders in review / closeout stage.")
    st.stop()

# ── Counters ──────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
metrics = [
    (c1, "Delivered",          "#2E7D32", "Delivered"),
    (c2, "Review Requested",   "#F57F17", "Awaiting Review"),
    (c3, "Review Received",    "#558B2F", "Review In"),
    (c4, "Closed Successfully","#1B5E20", "Closed ✓"),
    (c5, "POD Received",       "#00695C", "POD Received"),
]
for col, stage, color, label in metrics:
    n = len(df[df["Order Status"] == stage]) if "Order Status" in df.columns else 0
    col.markdown(
        f'<div style="background:#fff;border-top:3px solid {color};border-radius:8px;'
        f'padding:10px 12px;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,0.07)">'
        f'<div style="font-size:22px;font-weight:700;color:{BLACK}">{n}</div>'
        f'<div style="font-size:11px;color:#666">{label}</div>'
        f'</div>', unsafe_allow_html=True)

# Satisfaction breakdown
if "Customer Satisfaction Score" in df.columns:
    st.markdown("---")
    st.markdown("#### 📊 Satisfaction Scores")
    sc_counts = df["Customer Satisfaction Score"].value_counts()
    score_cols = st.columns(5)
    score_colors = {"5 Very Happy":"#1B5E20","4 Happy":"#388E3C","3 Neutral":"#F9A825",
                    "2 Not Happy":"#E65100","1 Complaint":"#B71C1C"}
    for col, score in zip(score_cols, SATISFACTION_SCORES):
        n = sc_counts.get(score, 0)
        c = score_colors.get(score,"#888")
        col.markdown(
            f'<div style="background:#fff;border-left:4px solid {c};border-radius:6px;'
            f'padding:10px 12px;box-shadow:0 1px 4px rgba(0,0,0,0.07)">'
            f'<div style="font-size:20px;font-weight:700;color:{BLACK}">{n}</div>'
            f'<div style="font-size:10px;color:#666">{score}</div>'
            f'</div>', unsafe_allow_html=True)

st.markdown("---")

# ── Table ─────────────────────────────────────────────────────────────────────
search = st.text_input("Search Order ID / Customer", "")
filtered = df.copy()
if search:
    mask = (
        filtered.get("Order ID", pd.Series()).astype(str).str.contains(search, case=False, na=False) |
        filtered.get("Customer Name", pd.Series()).astype(str).str.contains(search, case=False, na=False)
    )
    filtered = filtered[mask]

show_cols = [c for c in [
    "Order ID", "Order Date", "Customer Name", "Mobile Number",
    "Product Summary", "Total Amount",
    "Order Status", "Delivery Status", "Receiver Name", "Actual Received Date",
    "Customer Feedback", "Customer Satisfaction Score", "Review Permission",
    "Proof of Delivery",
] if c in filtered.columns]

st.dataframe(filtered[show_cols].reset_index(drop=True), use_container_width=True, height=240)

# ── Review & closeout form ────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Update Review & Close Order")

if not can_edit:
    st.caption("🔒 Owner / Admin or Sales / WhatsApp role required.")
    st.stop()

order_ids = filtered["Order ID"].dropna().astype(str).tolist()
if not order_ids:
    st.stop()

sel_id = st.selectbox("Select Order ID", order_ids)
order = filtered[filtered["Order ID"].astype(str) == sel_id]
if order.empty:
    st.stop()
o = order.iloc[0].to_dict()

st.markdown(f"**{o.get('Customer Name','')}** · {o.get('Product Summary','')} · "
            f"Status: {status_badge(str(o.get('Order Status','')))}",
            unsafe_allow_html=True)

col_a, col_b = st.columns(2)
with col_a:
    curr_score = str(o.get("Customer Satisfaction Score",""))
    new_score = st.selectbox("Customer Satisfaction Score",
                             [""] + SATISFACTION_SCORES,
                             index=([""]+SATISFACTION_SCORES).index(curr_score)
                             if curr_score in SATISFACTION_SCORES else 0)
    feedback = st.text_area("Customer Feedback", str(o.get("Customer Feedback","")), height=100)
    review_perm = st.selectbox("Review Permission", ["", "Yes", "No"],
                               index=["","Yes","No"].index(str(o.get("Review Permission","")))
                               if str(o.get("Review Permission","")) in ["","Yes","No"] else 0)

with col_b:
    phase3_notes = st.text_area("Phase 3 Notes", str(o.get("Phase 3 Notes","")), height=100)
    review_share = st.selectbox("Review Sharing Permission", ["", "Yes", "No"],
                                index=["","Yes","No"].index(str(o.get("Review Sharing Permission Phase3","")))
                                if str(o.get("Review Sharing Permission Phase3","")) in ["","Yes","No"] else 0)

# Quick actions
st.markdown("##### Actions")
qa1, qa2, qa3 = st.columns(3)

def _quick(label, col, upd):
    if col.button(label, key=f"rv_{label}_{sel_id}"):
        ok = update_master_order(sel_id, upd)
        if ok:
            st.success(f"✅ {label}")
            st.cache_data.clear()
            st.rerun()
        else:
            st.error("Update failed.")

_quick("📩 Request Review",
    qa1, {"Order Status": "Review Requested"})
_quick("✅ Review Received",
    qa2, {"Order Status": "Review Received"})
_quick("⚠️ Flag Issue",
    qa3, {"Order Status": "Issue / Return", "Risk Status": "High"})

# Save form
if st.button("💾 Save Review Update", type="primary"):
    updates = {
        "Customer Satisfaction Score":      new_score,
        "Customer Feedback":                feedback,
        "Review Permission":                review_perm,
        "Review Sharing Permission Phase3": review_share,
        "Phase 3 Notes":                    phase3_notes,
    }
    if new_score:
        updates["Order Status"] = "Review Received"
    ok = update_master_order(sel_id, updates)
    if ok:
        st.success("✅ Review saved.")
        st.cache_data.clear()
        st.rerun()
    else:
        st.error("❌ Update failed.")

st.markdown("---")

# ── Close order ───────────────────────────────────────────────────────────────
st.subheader("🏁 Close Order Successfully")
st.markdown("All conditions must be met:")

ds  = str(o.get("Delivery Status",""))
rn  = str(o.get("Receiver Name","")).strip()
ard = str(o.get("Actual Received Date","")).strip()
pod = str(o.get("Proof of Delivery","")).strip()
cs  = str(o.get("Customer Satisfaction Score","")).strip()

checks = {
    "✅ Delivery Status is Delivered or POD Received": ds in ["Delivered","POD Received"],
    "✅ Receiver Name completed":                       bool(rn),
    "✅ Actual Received Date completed":                bool(ard),
    "✅ Proof of Delivery provided":                    bool(pod),
    "✅ Customer Satisfaction Score recorded":          bool(cs),
}
all_ok = all(checks.values())

for label, passed in checks.items():
    icon = "✅" if passed else "❌"
    color = "#2E7D32" if passed else "#B71C1C"
    st.markdown(
        f'<div style="color:{color};padding:2px 0;font-size:14px">{icon} {label.split("✅ ")[1]}</div>',
        unsafe_allow_html=True)

st.markdown("")
if all_ok:
    if st.button("🏁 Close Successfully", type="primary"):
        ok = update_master_order(sel_id, {"Order Status": "Closed Successfully"})
        if ok:
            st.success("🎉 Order closed successfully!")
            st.balloons()
            st.cache_data.clear()
            st.rerun()
        else:
            st.error("Update failed.")
else:
    st.button("🔒 Close Successfully (conditions not met)", disabled=True)
