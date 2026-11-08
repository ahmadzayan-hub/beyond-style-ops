"""Verified Streamlit OIDC identity and server-owned authorization policy.

No role comes from widgets, query parameters, email claims or session_state.
The deployment owner configures issuer + subject roles in Streamlit secrets.
"""
from collections.abc import Mapping

from ops.config import ROLES

OWNER = "Owner / Admin"
SALES = "Sales / WhatsApp"
PACKING = "Packing / Sharon"
COURIER = "Courier / Delivery"

# Field boundaries preserve the existing role-specific pages. An unknown field
# or workflow state is denied until deliberately added to this policy.
MASTER_FIELDS = {
    SALES: {
        "Order Status", "Packing QC Status", "Payment Status", "COD Expected",
        "Customer Satisfaction Score", "Customer Feedback", "Review Permission",
        "Review Sharing Permission Phase3", "Phase 3 Notes", "Risk Status",
    },
    PACKING: {
        "Order Status", "Packing QC Status", "Dispatch Gate Status", "Internal Notes",
        "QC Photo Link", "Shipment Label Status", "Courier Status",
    },
    COURIER: {
        "Order Status", "Courier Company", "AWB / Tracking Number", "Courier Status",
        "Delivery Status", "Receiver Name", "Staff Number", "Actual Received Date",
        "Proof of Delivery", "Courier Notes",
    },
}
MASTER_VALUES = {
    SALES: {
        "Order Status": {
            "Critical Data Check", "QC Pending", "Payment Pending", "Payment Link Sent",
            "Paid Online", "COD Confirmed", "Review Requested", "Review Received",
            "Closed Successfully", "Issue / Return",
        },
        "Packing QC Status": {"Pending"},
        "Risk Status": {"High"},
    },
    PACKING: {
        "Order Status": {"Product Photo Sent", "Customer Approved", "Packed",
                         "Shipment Label Ready", "Courier Booked"},
        "Courier Status": {"Booked"},
    },
    COURIER: {
        "Order Status": {"Courier Booked", "Handed to Courier", "Out for Delivery",
                         "Delivered", "POD Received"},
    },
}
ACTION_ROLES = {
    "Process Order": {SALES}, "Send to QC": {SALES},
    "Mark Payment Link Sent": {SALES}, "Mark Paid Online": {SALES},
    "Mark COD Confirmed": {SALES}, "Request Review": {SALES},
    "Close Successfully": {SALES},
    "Photo Sent to Customer": {PACKING}, "Customer Approved": {PACKING},
    "Mark Packed": {PACKING}, "Mark Label Ready": {PACKING},
    "Courier Booked": {PACKING, COURIER}, "Handed to Courier": {COURIER},
    "Mark Delivered": {COURIER},
}
RESOURCE_WRITERS = {
    "Payments": {OWNER, SALES},
    "Packing QC": {OWNER, PACKING},
    "Courier Tracking": {OWNER, COURIER},
}

RESOURCE_FIELDS = {
    "Payments": {"Payment Status", "Payment Reference", "Payment Link", "COD Expected",
                 "COD Collected", "Notes"},
    "Packing QC": {"Packing QC Status", "Prepared By", "Prepared Date", "QC Notes",
                   "QC Photo Link", "Internal Notes"},
    "Courier Tracking": {"Courier Company", "AWB / Tracking Number", "Courier Status",
                         "Delivery Status", "Receiver Name", "Staff Number",
                         "Actual Received Date", "Proof of Delivery", "Courier Notes"},
}


def resolve_role(claims, policy, *, logged_in=False):
    """Resolve only a verified issuer/subject pair; absent/invalid policy denies."""
    if logged_in is not True or not isinstance(claims, Mapping) or not isinstance(policy, Mapping):
        return None
    issuer = policy.get("issuer")
    subject = claims.get("sub")
    roles = policy.get("user_roles")
    if not isinstance(issuer, str) or not issuer or claims.get("iss") != issuer:
        return None
    if not isinstance(subject, str) or not subject or not isinstance(roles, Mapping):
        return None
    role = roles.get(subject)
    return role if isinstance(role, str) and role in ROLES else None


def current_role():
    """Re-evaluate trusted identity/config on every request, including writes."""
    import streamlit as st
    try:
        user = st.user
        return resolve_role(dict(user), st.secrets.get("ops_auth", {}),
                            logged_in=user.is_logged_in)
    except (AttributeError, KeyError, TypeError, FileNotFoundError):
        return None


def assert_access():
    role = current_role()
    if role is None:
        raise PermissionError("An authorized, verified account is required.")
    return role


def require_access():
    """Gate every page before any cached or uncached operational data is read."""
    import streamlit as st
    role = current_role()
    if role is None:
        st.error("Sign in with an account authorized by the owner to access operations.")
        try:
            logged_in = st.user.is_logged_in
            configured = bool(st.secrets.get("auth", {})) and bool(st.secrets.get("ops_auth", {}))
        except (AttributeError, KeyError, TypeError, FileNotFoundError):
            logged_in, configured = False, False
        if logged_in:
            st.info("This account has no access. Ask the owner to check its assigned role.")
            if st.button("Sign out", key="ops_sign_out_denied"):
                st.logout()
        elif configured:
            if st.button("Sign in", key="ops_sign_in"):
                st.login()
        else:
            st.info("Owner setup is required before this dashboard can display operational data.")
        st.stop()
        # Defense in depth for test doubles or unexpected framework behavior.
        raise PermissionError("Operational access denied.")
    if st.sidebar.button("Sign out", key="ops_sign_out"):
        st.logout()
        st.stop()
        raise PermissionError("Signed out.")
    return role


def can_perform_action(role, action):
    return role == OWNER or role in ACTION_ROLES.get(action, set())


def authorize_update(role, resource, updates):
    """Pure policy, used at the Sheets write boundary, independent of UI state."""
    if role not in ROLES or role == "Read Only" or not isinstance(updates, dict) or not updates:
        raise PermissionError("This account cannot make this update.")
    if resource == "Master Orders":
        if role == OWNER:
            return
        if not set(updates).issubset(MASTER_FIELDS.get(role, set())):
            raise PermissionError("This role cannot update one or more requested fields.")
        for field, values in MASTER_VALUES.get(role, {}).items():
            if field in updates and updates[field] not in values:
                raise PermissionError("This role cannot set the requested workflow state.")
    else:
        if role not in RESOURCE_WRITERS.get(resource, set()):
            raise PermissionError("This role cannot update this worksheet.")
        if not set(updates).issubset(RESOURCE_FIELDS.get(resource, set())):
            raise PermissionError("This role cannot update one or more requested fields.")


def assert_update(resource, updates):
    authorize_update(assert_access(), resource, updates)
