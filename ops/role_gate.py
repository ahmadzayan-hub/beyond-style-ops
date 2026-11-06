"""ops/role_gate.py — Streamlit glue for ops/role_auth.py.

Every page calls require_role() before loading data. It returns the role the
session proved with a passcode, or stops the page.
"""

import streamlit as st

from ops.role_auth import (
    ROLE_ENV, attempt_allowed, configured_roles, dev_unlocked,
    record_attempt, verified_role, verify_role,
)


def require_role() -> str:
    role = verified_role(st.session_state)
    if role is None:
        st.warning("🔒 Sign in from the Dashboard sidebar to open this page.")
        st.stop()
    if dev_unlocked():
        st.error("Development mode: roles are not checked (OPS_DEV_UNLOCKED=1). Do not use with live data.")
    return role


def sidebar_sign_in(role_colors: dict, default_color: str) -> None:
    """Sign-in or signed-in badge. Call inside `with st.sidebar:`."""
    role = verified_role(st.session_state)
    if role:
        color = role_colors.get(role, default_color)
        st.markdown(
            f'<div style="background:{color};color:#fff;padding:6px 12px;'
            f'border-radius:6px;font-size:12px;font-weight:600;text-align:center">'
            f'Signed in: {role}</div>', unsafe_allow_html=True)
        if st.button("Sign out"):
            for key in ("auth_role", "role"):
                st.session_state.pop(key, None)
            st.rerun()
        return

    roles = configured_roles()
    if not roles:
        st.error("No role passcodes are configured. Set the OPS_PASSCODE_* variables on the server.")
        return
    with st.form("sign_in"):
        choice = st.selectbox("👤 Role", roles)
        passcode = st.text_input("Passcode", type="password")
        submitted = st.form_submit_button("Sign in")
    if not submitted:
        return
    if not attempt_allowed(st.session_state):
        st.error("Too many failed attempts. Wait a minute and try again.")
        return
    ok = verify_role(choice, passcode)
    record_attempt(st.session_state, ok)
    if ok:
        st.session_state["auth_role"] = choice
        st.session_state["role"] = choice
        st.rerun()
    else:
        st.error("Wrong passcode for that role.")


__all__ = ["require_role", "sidebar_sign_in", "ROLE_ENV"]
