"""
PE Org-AI-R Platform — Streamlit UI (Case Study 2: Evidence Collection).

Run from project root: poetry run streamlit run streamlit_ui/main.py
Or from streamlit_ui/: streamlit run main.py
Set STREAMLIT_API_URL to use a different backend (default: http://35.93.9.162:8000)
"""
import sys
from pathlib import Path

# Ensure project root is on path when run as "streamlit run main.py" from streamlit_ui/
_root = Path(__file__).resolve().parent.parent
if _root not in sys.path:
    sys.path.insert(0, str(_root))

import streamlit as st

st.set_page_config(
    page_title="PE Org-AI-R Platform",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("PE Org-AI-R Platform")
st.caption("AI Readiness Assessment for Private Equity — Case Study 2: Evidence Collection")

st.markdown("""
**What companies say (SEC filings) vs. what they do (external signals).**

Use the **sidebar** to open:

- **Companies** — List, add, and update companies (industry, URLs for signal pipeline)
- **Dashboard** — Evidence stats, target companies, breakdowns
- **Documents** — SEC filings list, detail, chunks, and JSON
- **Signals** — External signals list, company summary, JSON
- **Evidence** — Full evidence per company, trigger backfill
- **Logs** — Run collection from the UI and view live logs
- **JSON Data** — Call any endpoint and view raw JSON
""")

st.info("Ensure the FastAPI backend is running (e.g. `poetry run uvicorn app.main:app --reload`) and set `STREAMLIT_API_URL` if needed.")
