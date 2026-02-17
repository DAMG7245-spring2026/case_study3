"""Dashboard: evidence stats and target companies."""
import streamlit as st

from streamlit_ui.components.api_client import get_client, get_evidence_stats, get_target_companies
from streamlit_ui.components.json_viewer import render_json
from streamlit_ui.utils.config import get_api_url


st.set_page_config(page_title="Dashboard | PE Org-AI-R", page_icon="📊", layout="wide")
st.title("Dashboard")
st.caption("Evidence collection statistics and target companies")

api_url = get_api_url()
client = get_client()

try:
    stats = get_evidence_stats(client)
    companies_data = get_target_companies(client)
except Exception as e:
    st.error(f"Cannot reach API at {api_url}. Is the backend running? Error: {e}")
    st.stop()

# Metrics
st.subheader("Summary")
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Companies (target)", stats.get("total_companies", 0))
col2.metric("Documents", stats.get("total_documents", 0))
col3.metric("Chunks", stats.get("total_chunks", 0))
col4.metric("Signals", stats.get("total_signals", 0))
col5.metric("Companies w/ docs", stats.get("companies_with_documents", 0))

st.metric("Companies with signals", stats.get("companies_with_signals", 0))

# Breakdowns
tab1, tab2, tab3 = st.tabs(["Documents by type", "Documents by status", "Signals by category"])
with tab1:
    by_type = stats.get("documents_by_type") or {}
    if by_type:
        st.bar_chart(by_type)
    else:
        st.caption("No data")
with tab2:
    by_status = stats.get("documents_by_status") or {}
    if by_status:
        st.bar_chart(by_status)
    else:
        st.caption("No data")
with tab3:
    by_cat = stats.get("signals_by_category") or {}
    if by_cat:
        st.bar_chart(by_cat)
    else:
        st.caption("No data")

# Target companies table
st.subheader("Target companies")
companies_list = companies_data.get("companies") or []
if companies_list:
    st.dataframe(companies_list, use_container_width=True, hide_index=True)
else:
    st.caption("No target companies returned.")

# Raw JSON
render_json(stats, "View stats JSON", expanded=False)
render_json(companies_data, "View target companies JSON", expanded=False)

client.close()
