"""Shared dashboard handling for unsuccessful or uncertain saves."""
import streamlit as st


def show_update_error(result):
    if result.uncertain:
        # The entire batch may have committed. A user's next refresh must read
        # persisted data, not the previous 60-second page snapshot. Never retry.
        st.cache_data.clear()
    st.error(result.message)
