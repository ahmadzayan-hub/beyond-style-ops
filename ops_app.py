"""
ops_app.py — Beyond Style UAE | Order Operations Control
Main dashboard. Run with: streamlit run ops_app.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import pandas as pd
from ops.config import (
    ORDER_STAGES, STATUS_COLOR, ROLES, ROLE_COLORS,
    GOLD, BLACK, BEIGE, LIGHT, status_badge
)
from ops.sheets import get_master_orders, get_dashboard_counts

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Beyond Style UAE | Ops",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

  html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
  .main {{ background: {LIGHT}; }}

  /* Header */
  .bs-header {{
    background: {BLACK};
    color: #fff;
    padding: 18px 28px;
    border-radius: 12px;
    margin-bottom: 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .bs-header h1 {{ margin:0; font-size:22px; font-weight:700; color:#fff; }}
  .bs-header .tagline {{ color:{GOLD}; font-size:13px; margin-top:2px; }}
  .bs-header .meta {{ text-align:right; color:#aaa; font-size:12px; }}

  /* KPI cards */
  .kpi-card {{
    background: #fff;
    border-radius: 10px;
    padding: 18px 20px;
    border-left: 4px solid {GOLD};
    box-shadow: 0 1px 4px rgba(0,0,0,0.07);
    margin-bottom: 12px;
  }}
  .kpi-card .kpi-num {{ font-size: 32px; font-weight: 700; color: {BLACK}; line-height:1; }}
  .kpi-card .kpi-label {{ font-size: 12px; color: #666; margin-top: 4px; text-transform: uppercase; letter-spacing: .5px; }}
  .kpi-card.red {{ border-left-color: #C62828; }}
  .kpi-card.amber {{ border-left-color: #E65100; }}
  .kpi-card.green {{ border-left-color: #2E7D32; }}
  .kpi-card.blue {{ border-left-color: #1565C0; }}
  .kpi-card.gold {{ border-left-color: {GOLD}; }}

  /* Status sections */
  .section-title {{
    font-size: 13px; font-weight: 600; color: #888;
    text-transform: uppercase; letter-spacing: 1px;
    margin: 24px 0 12px;
    border-bottom: 1px solid #eee; padding-bottom: 6px;
  }}

  /* Stage pill */
  .stage-pill {{
    display:inline-block; padding: 4px 12px; border-radius: 20px;
    font-size: 12px; font-weight: 600; color: #fff; margin: 3px 4px 3px 0;
  }}

  /* Sidebar */
  section[data-testid="stSidebar"] {{
    background: {BLACK} !important;
  }}
  section[data-testid="stSidebar"] * {{ color: #fff !important; }}
  section[data-testid="stSidebar"] .stSelectbox label {{ color: {GOLD} !important; }}

  /* Buttons */
  .stButton > button {{
    background: {GOLD}; color: {BLACK}; border: none;
    font-weight: 600; border-radius: 8px; padding: 8px 20px;
  }}
  .stButton > button:hover {{ background: #b8932d; color: #fff; }}

  /* Table */
  .dataframe {{ font-size: 13px; }}

  /* Mobile adjustments */
  @media (max-width: 768px) {{
    .bs-header h1 {{ font-size: 16px; }}
    .kpi-card .kpi-num {{ font-size: 26px; }}
  }}
</style>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ✦ Beyond Style UAE")
    st.markdown("---")

    role = st.selectbox("👤 Your Role", ROLES,
                        index=ROLES.index(st.session_state.get("role", ROLES[0])))
    st.session_state["role"] = role
    role_c = ROLE_COLORS.get(role, GOLD)
    st.markdown(
        f'<div style="background:{role_c};color:#fff;padding:6px 12px;'
        f'border-radius:6px;font-size:12px;font-weight:600;text-align:center">'
        f'{role}</div>', unsafe_allow_html=True
    )

    st.markdown("---")
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.markdown("**Navigation**")
    st.page_link("ops_app.py",               label="🏠 Dashboard",      icon=None)
    st.page_link("pages/1_Orders.py",        label="📋 Orders",         icon=None)
    st.page_link("pages/2_Payments.py",      label="💳 Payments",       icon=None)
    st.page_link("pages/3_Packing_QC.py",    label="📦 Packing QC",     icon=None)
    st.page_link("pages/4_Labels.py",        label="🏷️ Labels",         icon=None)
    st.page_link("pages/5_Courier.py",       label="🚚 Courier",        icon=None)
    st.page_link("pages/6_Reviews.py",       label="⭐ Reviews",        icon=None)

    st.markdown("---")
    st.markdown('<p style="font-size:11px;color:#888">Beyond Style UAE<br>+971 55 155 6991<br>beyondstyle.ae</p>',
                unsafe_allow_html=True)


# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_orders():
    return get_master_orders()


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="bs-header">
  <div>
    <h1>✦ Beyond Style UAE</h1>
    <div class="tagline">Order Operations Control Centre</div>
  </div>
  <div class="meta">Live · Google Sheets<br>Master Orders</div>
</div>
""", unsafe_allow_html=True)

# ── Load + counts ─────────────────────────────────────────────────────────────
with st.spinner("Loading orders..."):
    df = load_orders()

if df.empty:
    st.warning("No orders found in Master Orders sheet.")
    st.stop()

counts = get_dashboard_counts(df)

# ── KPI row 1 — top-level ─────────────────────────────────────────────────────
st.markdown('<div class="section-title">Overall</div>', unsafe_allow_html=True)
c1, c2, c3, c4, c5 = st.columns(5)

def kpi(col, num, label, cls=""):
    col.markdown(
        f'<div class="kpi-card {cls}">'
        f'<div class="kpi-num">{num}</div>'
        f'<div class="kpi-label">{label}</div>'
        f'</div>', unsafe_allow_html=True
    )

kpi(c1, counts.get("_total", 0),          "Total Orders",      "gold")
kpi(c2, counts.get("_payment_pend", 0),   "Payment Pending",   "amber")
kpi(c3, counts.get("_paid_online", 0),    "Paid Online",       "green")
kpi(c4, counts.get("_cod_conf", 0),       "COD Confirmed",     "blue")
kpi(c5, counts.get("_high_risk", 0),      "High Risk",         "red")

# ── KPI row 2 — operations ────────────────────────────────────────────────────
st.markdown('<div class="section-title">Operations Pipeline</div>', unsafe_allow_html=True)

ops_stages = [
    ("New Form Order",      "New Orders",       "blue"),
    ("QC Pending",          "QC Pending",       "amber"),
    ("Customer Approved",   "Cust. Approved",   "green"),
    ("Packed",              "Packed",           "green"),
    ("Shipment Label Ready","Label Ready",      "blue"),
    ("Handed to Courier",   "With Courier",     "blue"),
]
cols = st.columns(6)
for col, (stage, label, cls) in zip(cols, ops_stages):
    kpi(col, counts.get(stage, 0), label, cls)

# ── KPI row 3 — delivery ──────────────────────────────────────────────────────
st.markdown('<div class="section-title">Delivery & Closeout</div>', unsafe_allow_html=True)

delivery_stages = [
    ("Out for Delivery",  "Out for Delivery", "blue"),
    ("Delivered",         "Delivered",        "green"),
    ("POD Received",      "POD Received",     "green"),
    ("Review Requested",  "Review Requested", "amber"),
    ("Closed Successfully","Closed",          "green"),
    ("Issue / Return",    "Issues",           "red"),
]
cols2 = st.columns(6)
for col, (stage, label, cls) in zip(cols2, delivery_stages):
    kpi(col, counts.get(stage, 0), label, cls)

if counts.get("_pod_missing", 0):
    st.warning(f"⚠️ **{counts['_pod_missing']} delivered orders missing Proof of Delivery** — check Courier tab.")

# ── Full stage breakdown ───────────────────────────────────────────────────────
with st.expander("📊 All Stages Breakdown", expanded=False):
    stage_data = []
    for stage in ORDER_STAGES:
        n = counts.get(stage, 0)
        color = STATUS_COLOR.get(stage, "#888")
        stage_data.append({"Stage": stage, "Count": n, "Color": color})

    sdf = pd.DataFrame(stage_data)
    sdf_nonzero = sdf[sdf["Count"] > 0].copy()

    col_a, col_b = st.columns([2, 1])
    with col_a:
        for _, row in sdf_nonzero.iterrows():
            badge = f'<span class="stage-pill" style="background:{row["Color"]}">{row["Stage"]}</span>'
            st.markdown(
                f'{badge} <strong>{int(row["Count"])}</strong>',
                unsafe_allow_html=True
            )
    with col_b:
        st.dataframe(sdf_nonzero[["Stage", "Count"]].set_index("Stage"), use_container_width=True)

# ── Recent orders ─────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">Recent Orders (Last 20)</div>', unsafe_allow_html=True)

show_cols = ["Order ID", "Order Date", "Customer Name", "Product Summary",
             "Total Amount", "Payment Status", "Order Status", "Risk Status"]
available = [c for c in show_cols if c in df.columns]
recent = df[available].tail(20).iloc[::-1]

# Color-code Order Status column
def highlight_status(val):
    color = STATUS_COLOR.get(str(val), "")
    if color:
        return f"background-color:{color}20;color:{color};font-weight:600"
    return ""

st.dataframe(
    recent.style.map(highlight_status, subset=["Order Status"] if "Order Status" in recent.columns else []),
    use_container_width=True,
    height=420,
)

st.caption(f"Showing last 20 of {len(df)} orders · Auto-refreshes every 60s · Click 🔄 in sidebar for instant refresh")
