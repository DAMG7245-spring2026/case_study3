"""JSON Data: call endpoint and view raw JSON."""
from uuid import UUID

import streamlit as st

from streamlit_ui.components.api_client import (
    get_client,
    get_company_evidence,
    get_company_signal_summary,
    get_company_options,
    get_document,
    get_document_chunks,
    get_documents,
    get_evidence_stats,
    get_signals,
    get_target_companies,
    get_ticker_to_company_id,
)
from streamlit_ui.components.json_viewer import render_json
from streamlit_ui.utils.config import get_api_url

st.set_page_config(page_title="JSON Data | PE Org-AI-R", page_icon="{}", layout="wide")
st.title("JSON Data")
st.caption("Call an endpoint and view raw JSON")

api_url = get_api_url()
client = get_client()
ticker_to_id = get_ticker_to_company_id(client)
json_ticker_options, json_ticker_labels = get_company_options(client)

entity = st.selectbox(
    "Entity",
    [
        "Evidence stats",
        "Target companies",
        "Documents (paginated)",
        "Document by ID",
        "Document chunks",
        "Signals (paginated)",
        "Company signal summary",
        "Company evidence",
    ],
)

data = None
error = None

try:
    if entity == "Evidence stats":
        data = get_evidence_stats(client)
    elif entity == "Target companies":
        data = get_target_companies(client)
    elif entity == "Documents (paginated)":
        col1, col2, col3 = st.columns(3)
        with col1:
            page = st.number_input("Page", min_value=1, value=1, key="json_docs_page")
        with col2:
            page_size = st.number_input("Page size", min_value=1, max_value=100, value=20, key="json_docs_ps")
        with col3:
            ticker = st.selectbox(
                "Ticker filter",
                json_ticker_options,
                format_func=lambda x: "Any" if not x else json_ticker_labels.get(x, x),
                key="json_docs_ticker",
            )
        data = get_documents(
            client,
            page=page,
            page_size=page_size,
            ticker=(ticker.strip() if ticker else None),
        )
    elif entity == "Document by ID":
        doc_id = st.text_input("Document ID (UUID)", key="json_doc_id")
        if doc_id.strip():
            data = get_document(UUID(doc_id.strip()), client)
        else:
            st.info("Enter a document UUID.")
    elif entity == "Document chunks":
        doc_id = st.text_input("Document ID (UUID)", key="json_chunks_doc_id")
        page = st.number_input("Page", min_value=1, value=1, key="json_chunks_page")
        if doc_id.strip():
            data = get_document_chunks(UUID(doc_id.strip()), client, page=page, page_size=50)
        else:
            st.info("Enter a document UUID.")
    elif entity == "Signals (paginated)":
        col1, col2 = st.columns(2)
        with col1:
            page = st.number_input("Page", min_value=1, value=1, key="json_sig_page")
        with col2:
            page_size = st.number_input("Page size", min_value=1, max_value=100, value=20, key="json_sig_ps")
        data = get_signals(client, page=page, page_size=page_size)
    elif entity == "Company signal summary":
        ticker = st.selectbox(
            "Company (ticker)",
            json_ticker_options,
            format_func=lambda x: "Select..." if not x else json_ticker_labels.get(x, x),
            key="json_summary_ticker",
        )
        company_id = ticker_to_id.get(ticker) if ticker else ""
        if ticker and company_id:
            data = get_company_signal_summary(UUID(company_id), client)
            if data is None:
                data = {"message": "No summary for this company."}
        elif ticker:
            st.info("Company not in DB yet.")
        else:
            st.info("Select a company.")
    elif entity == "Company evidence":
        ticker = st.selectbox(
            "Company (ticker)",
            json_ticker_options,
            format_func=lambda x: "Select..." if not x else json_ticker_labels.get(x, x),
            key="json_evidence_ticker",
        )
        company_id = ticker_to_id.get(ticker) if ticker else ""
        if ticker and company_id:
            data = get_company_evidence(UUID(company_id), client)
        elif ticker:
            st.info("Company not in DB yet.")
        else:
            st.info("Select a company.")
except Exception as e:
    error = str(e)

if error:
    st.error(f"Request failed: {error}")
elif data is not None:
    render_json(data, "Response (expand to copy)", expanded=True)

client.close()
