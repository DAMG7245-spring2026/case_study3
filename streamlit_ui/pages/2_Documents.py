"""Documents: run pipeline and view server logs."""
import streamlit as st

from streamlit_ui.components.api_client import (
    get_client,
    get_companies,
    collect_documents,
    collect_documents_all,
    get_document_collection_logs,
)
from streamlit_ui.utils.config import get_api_url

st.set_page_config(page_title="Documents | PE Org-AI-R", page_icon="📄", layout="wide")
st.title("Documents")
st.caption("Run the documents pipeline for a company and view server logs below.")

api_url = get_api_url()
client = get_client()

# --- Run documents pipeline ---
st.subheader("Run documents pipeline")
companies_data = get_companies(client)
companies_items = companies_data.get("items") or []
company_options = [(f"{c.get('ticker', '')} — {c.get('name', '')}", str(c["id"])) for c in companies_items if c.get("id") and c.get("ticker")]
FILING_TYPES = ["10-K", "10-Q", "8-K", "DEF-14A"]

run_scope = st.radio(
    "Run for",
    options=["One company", "All companies"],
    index=0,
    key="doc_run_scope",
    horizontal=True,
)
if not company_options and run_scope == "One company":
    st.caption("Add at least one company (Companies page) to run the pipeline.")
elif run_scope == "All companies" and not company_options:
    st.caption("Add at least one company (Companies page) to run the pipeline for all.")
else:
    with st.form("run_documents_pipeline"):
<<<<<<< HEAD
        company_labels = [x[0] for x in company_options]
        company_ids = [x[1] for x in company_options]
        sel_idx = st.selectbox("Company", range(len(company_labels)), format_func=lambda i: company_labels[i], key="run_company_select")
        COMMON_FILING_TYPES = ["10-K", "10-Q", "8-K", "DEF 14A"]
        selected_filings = st.multiselect(
            "Filing types",
            options=COMMON_FILING_TYPES,
            default=["10-K", "10-Q", "8-K"],
            key="filing_types_multi",
        )
        custom_input = st.text_input(
            "Other filing types (comma-separated, e.g. S-1, 20-F)",
            value="",
            key="filing_types_custom",
        )
=======
        if run_scope == "One company":
            company_labels = [x[0] for x in company_options]
            company_ids = [x[1] for x in company_options]
            sel_idx = st.selectbox("Company", range(len(company_labels)), format_func=lambda i: company_labels[i], key="run_company_select")
        st.caption("Select which filing types to collect:")
        filing_10k = st.checkbox("10-K", value=True, key="ft_10k")
        filing_10q = st.checkbox("10-Q", value=True, key="ft_10q")
        filing_8k = st.checkbox("8-K", value=True, key="ft_8k")
        filing_def14a = st.checkbox("DEF-14A", value=False, key="ft_def14a")
>>>>>>> main
        years_back = st.number_input("Years back", min_value=1, max_value=10, value=3, key="years_back_run")
        run_clicked = st.form_submit_button("Run documents pipeline")
    if run_clicked:
        extra = [t.strip().upper() for t in custom_input.split(",") if t.strip()]
        selected_filings = list(dict.fromkeys(selected_filings + extra))
        if not selected_filings:
            st.error("Select at least one filing type.")
        else:
            try:
                if run_scope == "All companies":
                    resp = collect_documents_all(selected_filings, years_back=years_back, client=client)
                else:
                    company_id = company_ids[sel_idx]
                    resp = collect_documents(company_id, selected_filings, years_back=years_back, client=client)
                task_id = resp.get("task_id", "")
                st.session_state["documents_task_id"] = task_id
                st.success(resp.get("message", "Collection started. Server logs will appear below (scrollable)."))
            except Exception as e:
                st.error(f"Failed to start collection: {e}")

    # Pipeline log: fetch on load or when Refresh is clicked (no auto-polling)
    task_id = st.session_state.get("documents_task_id")
    if task_id:
        st.markdown("**Pipeline log**")
        if st.button("Refresh log", key="documents_refresh_log"):
            st.rerun()
        try:
            data = get_document_collection_logs(task_id, client=client)
            logs = data.get("logs") or []
            finished = data.get("finished", False)
        except Exception:
            logs = ["(Could not fetch logs from server.)"]
            finished = False
        status = " (finished)" if finished else " (running)"
        st.caption(f"Task status:{status} Click Refresh log to update.")
        log_text = "\n".join(logs) if logs else "(waiting for logs…)"
        st.text_area(
            "Log output",
            value=log_text,
            height=220,
            disabled=True,
            label_visibility="collapsed",
            key="documents_pipeline_log_output",
        )

client.close()
