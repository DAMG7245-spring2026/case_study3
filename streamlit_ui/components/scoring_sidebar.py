"""Shared scoring sidebar: company selector and Run Pipeline button. Writes session state for scoring views."""
from typing import Any, Optional

import streamlit as st

from streamlit_ui.components.api_client import (
    get_client,
    get_companies,
    get_dimension_scores,
    post_score_by_ticker,
)


# Session state keys
KEY_TICKER = "scoring_selected_ticker"
KEY_COMPANY_ID = "scoring_selected_company_id"
KEY_LAST_RESULT = "scoring_last_result"
KEY_DIMENSION_DETAILS = "scoring_dimension_details"
KEY_PIPELINE_MESSAGE = "scoring_pipeline_message"


def init_scoring_session_state() -> None:
    """Initialize scoring-related keys in session state if not set."""
    if KEY_TICKER not in st.session_state:
        st.session_state[KEY_TICKER] = ""
    if KEY_COMPANY_ID not in st.session_state:
        st.session_state[KEY_COMPANY_ID] = ""
    if KEY_LAST_RESULT not in st.session_state:
        st.session_state[KEY_LAST_RESULT] = None
    if KEY_DIMENSION_DETAILS not in st.session_state:
        st.session_state[KEY_DIMENSION_DETAILS] = None
    if KEY_PIPELINE_MESSAGE not in st.session_state:
        st.session_state[KEY_PIPELINE_MESSAGE] = None


def render_scoring_sidebar() -> None:
    """
    Render company selector and Run Pipeline button in the sidebar.
    Updates scoring_selected_ticker, scoring_selected_company_id, scoring_last_result,
    scoring_dimension_details, and scoring_pipeline_message.
    """
    init_scoring_session_state()

    st.sidebar.subheader("Scoring")
    client = get_client()

    try:
        data = get_companies(client, page=1, page_size=100)
    except Exception:
        st.sidebar.caption("Could not load companies. Is the API running?")
        client.close()
        return

    items = data.get("items") or []
    ticker_to_id = {str(c.get("ticker", "")): str(c["id"]) for c in items if c.get("id") and c.get("ticker")}
    ticker_options = [""] + [str(c.get("ticker", "")) for c in items if c.get("ticker")]
    ticker_labels = {t: f"{t} — {next((c.get('name', t) for c in items if str(c.get('ticker', '')) == t), t)}" for t in ticker_options if t}

    selected = st.sidebar.selectbox(
        "Company (ticker)",
        ticker_options,
        format_func=lambda x: "Select..." if not x else ticker_labels.get(x, x),
        key="scoring_company_select",
    )

    if selected:
        st.session_state[KEY_TICKER] = selected
        st.session_state[KEY_COMPANY_ID] = ticker_to_id.get(selected, "")
    else:
        st.session_state[KEY_TICKER] = ""
        st.session_state[KEY_COMPANY_ID] = ""

    run_disabled = not (st.session_state[KEY_TICKER] and st.session_state[KEY_COMPANY_ID])
    if st.sidebar.button("Run Pipeline", type="primary", disabled=run_disabled, key="scoring_run_pipeline"):
        ticker = st.session_state[KEY_TICKER]
        st.session_state[KEY_PIPELINE_MESSAGE] = None
        st.session_state[KEY_LAST_RESULT] = None
        st.session_state[KEY_DIMENSION_DETAILS] = None
        with st.sidebar.spinner("Running pipeline..."):
            try:
                result = post_score_by_ticker(ticker, client=client)
                st.session_state[KEY_LAST_RESULT] = result
                dim_list = get_dimension_scores(st.session_state[KEY_COMPANY_ID], client=client)
                st.session_state[KEY_DIMENSION_DETAILS] = dim_list if isinstance(dim_list, list) else []
                st.session_state[KEY_PIPELINE_MESSAGE] = ("success", f"Pipeline completed for {ticker}.")
            except Exception as e:
                st.session_state[KEY_PIPELINE_MESSAGE] = ("error", str(e))

    msg = st.session_state.get(KEY_PIPELINE_MESSAGE)
    if msg:
        kind, text = msg
        if kind == "success":
            st.sidebar.success(text)
        else:
            st.sidebar.error(text)

    client.close()


def get_last_result() -> Optional[dict[str, Any]]:
    """Return last pipeline result from session state."""
    init_scoring_session_state()
    return st.session_state.get(KEY_LAST_RESULT)


def get_dimension_details() -> Optional[list]:
    """Return dimension score details from session state."""
    init_scoring_session_state()
    return st.session_state.get(KEY_DIMENSION_DETAILS)


def get_selected_company_id() -> str:
    """Return selected company ID from session state."""
    init_scoring_session_state()
    return st.session_state.get(KEY_COMPANY_ID) or ""


def get_selected_ticker() -> str:
    """Return selected ticker from session state."""
    init_scoring_session_state()
    return st.session_state.get(KEY_TICKER) or ""
