"""Reusable JSON display for API responses and parsed data."""
import json
import streamlit as st
from typing import Any


def render_json(data: Any, label: str = "View as JSON", expanded: bool = False) -> None:
    """
    Render dict/list as JSON in an expander (st.json + optional code block).
    Use for "View as JSON" next to formatted views.
    """
    if data is None:
        st.caption("No data")
        return
    try:
        if isinstance(data, (dict, list)):
            json_str = json.dumps(data, indent=2, default=str)
        else:
            json_str = str(data)
    except (TypeError, ValueError):
        json_str = str(data)
    with st.expander(label, expanded=expanded):
        st.json(data if isinstance(data, (dict, list)) else {"raw": json_str})
        st.code(json_str, language="json")
