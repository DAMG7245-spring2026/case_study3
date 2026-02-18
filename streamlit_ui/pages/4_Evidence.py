"""Evidence: company evidence view and backfill trigger."""
from uuid import UUID

import streamlit as st

from streamlit_ui.components.api_client import (
    get_client,
    get_company_evidence,
    get_company_options,
    get_ticker_to_company_id,
    post_backfill,
)
from streamlit_ui.components.json_viewer import render_json
from streamlit_ui.utils.config import get_api_url

st.set_page_config(page_title="Evidence | PE Org-AI-R", page_icon="📁", layout="wide")
st.title("Evidence")
st.caption("Company evidence and backfill")

api_url = get_api_url()
client = get_client()
ticker_to_id = get_ticker_to_company_id(client)
ticker_options, ticker_labels = get_company_options(client)

# Evidence view
st.subheader("Company evidence")
selected_ticker = st.selectbox(
    "Company (ticker)",
    ticker_options,
    format_func=lambda x: "Select..." if not x else ticker_labels.get(x, x),
)
selected_id = ticker_to_id.get(selected_ticker) if selected_ticker else None
if not selected_ticker:
    st.caption("Select a company to view evidence.")
elif not selected_id:
    st.info("Company not in DB yet. Run backfill to add companies.")
elif selected_id:
    try:
        evidence = get_company_evidence(UUID(selected_id), client)
        st.metric("Documents", evidence.get("document_count", 0))
        st.metric("Chunks", evidence.get("chunk_count", 0))
        summary = evidence.get("signal_summary")
        if summary:
            st.metric("Composite signal score", summary.get("composite_score"))
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Hiring", summary.get("technology_hiring_score"))
            c2.metric("Innovation", summary.get("innovation_activity_score"))
            c3.metric("Digital", summary.get("digital_presence_score"))
            c4.metric("Leadership", summary.get("leadership_signals_score"))
        signals = evidence.get("signals") or []
        st.write(f"Signals: {len(signals)}")
        if signals:
            st.dataframe(
                [
                    {
                        "category": s.get("category"),
                        "source": s.get("source"),
                        "raw_value": (s.get("raw_value") or "")[:50],
                        "score": s.get("normalized_score"),
                    }
                    for s in signals
                ],
                use_container_width=True,
                hide_index=True,
            )
        render_json(evidence, "View full evidence JSON", expanded=False)
    except Exception as e:
        st.error(f"Failed to load evidence: {e}")

# Backfill
st.subheader("Trigger backfill")
backfill_tickers = [t for t in ticker_options if t]
with st.form("backfill_form"):
    selected_tickers = st.multiselect(
        "Companies (select none = all)",
        options=backfill_tickers,
        format_func=lambda x: ticker_labels.get(x, x),
        help="Select one or more companies. Leave empty to run for all.",
    )
    include_documents = st.checkbox("Include documents", value=True)
    include_signals = st.checkbox("Include signals", value=True)
    years_back = st.slider("Years back", 1, 10, 3)
    COMMON_FILING_TYPES = ["10-K", "10-Q", "8-K", "DEF 14A"]
    filing_types_sel = st.multiselect(
        "Filing types (documents)",
        options=COMMON_FILING_TYPES,
        default=["10-K", "10-Q", "8-K"],
        key="backfill_filing_types",
    )
    custom_ft = st.text_input(
        "Other filing types (comma-separated)",
        value="",
        key="backfill_custom_ft",
    )
    submitted = st.form_submit_button("Run backfill")
    if submitted:
        tickers = selected_tickers if selected_tickers else None
        extra_ft = [t.strip().upper() for t in custom_ft.split(",") if t.strip()]
        merged_filing_types = list(dict.fromkeys(filing_types_sel + extra_ft))
        try:
            resp = post_backfill(
                tickers=tickers,
                include_documents=include_documents,
                include_signals=include_signals,
                years_back=years_back,
                filing_types=merged_filing_types if merged_filing_types else None,
                client=client,
            )
            st.success(resp.get("message", "Backfill queued."))
            st.write("Task ID:", resp.get("task_id"))
            render_json(resp, "Backfill response JSON", expanded=True)
        except Exception as e:
            st.error(f"Backfill request failed: {e}")

client.close()
