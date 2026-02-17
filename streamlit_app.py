"""
Launcher for the Streamlit Evidence Collection UI.

To run the full UI (Dashboard, Documents, Signals, Evidence, Logs, JSON Data), use:

    poetry run streamlit run streamlit_ui/main.py

Set STREAMLIT_API_URL to override the default backend (http://35.93.9.162:8000)
"""
import streamlit as st

st.set_page_config(page_title="PE Org-AI-R Platform", page_icon="📊", layout="wide")
st.title("PE Org-AI-R Platform")
st.caption("AI Readiness Assessment for Private Equity — Case Study 2: Evidence Collection")

st.info(
    "**Run the full UI:** `poetry run streamlit run streamlit_ui/main.py`\n\n"
    "Ensure the FastAPI backend is running (e.g. `poetry run uvicorn app.main:app --reload`). "
    "Set `STREAMLIT_API_URL` to use a different backend (default: http://35.93.9.162:8000)"
)
