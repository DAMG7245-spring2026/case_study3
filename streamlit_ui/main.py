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
st.caption("AI Readiness Assessment for Private Equity — Scoring Flow & Evidence")

st.markdown("""
**What companies say (SEC filings) vs. what they do (external signals).**

Use the **sidebar** to open:

**Scoring (select company + Run Pipeline):**
- **Scoring Dashboard** — Org-AI-R, V^R, H^R, Synergy, 7-dimension chart, CI, TC, PF
- **Evidence Pipeline** — CS2/CS3 signals and coverage summary
- **Dimension Scoring** — Signal-to-dimension mapping, rubric results
- **Portfolio View** — Compare up to 5 companies (table + bar charts)
- **Audit Trail** — Step-by-step pipeline breakdown
- **Org-AI-R Calculator** — Company Details form: manual V^R, H^R, Synergy, CI inputs → calculate score

**Data:**
- **Companies** — List, add, and update companies
- **Dashboard** — Evidence stats, target companies
- **Documents** — SEC filings list and detail
- **Signals** — External signals, collect and compute
- **Evidence** — Full evidence per company, backfill
""")

st.info("Ensure the FastAPI backend is running (e.g. `poetry run uvicorn app.main:app --reload`) and set `STREAMLIT_API_URL` if needed.")
