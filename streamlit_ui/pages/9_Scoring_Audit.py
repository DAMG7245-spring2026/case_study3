"""Audit Trail: step-by-step pipeline breakdown with key values from last result."""
import streamlit as st

from streamlit_ui.components.scoring_sidebar import get_last_result, render_scoring_sidebar

st.set_page_config(page_title="Audit Trail | PE Org-AI-R", page_icon="📋", layout="wide")
render_scoring_sidebar()

st.title("Audit Trail")
st.caption("Step-by-step calculation breakdown")

result = get_last_result()

STEPS = [
    ("1. Fetch company", "Company resolved by ticker"),
    ("2. Fetch evidence", "CS2 evidence (documents + signals)"),
    ("3. Build evidence scores", "EvidenceScore list from signals"),
    ("4. Dimension scoring", "EvidenceMapper + RubricScorer → 7 dimensions"),
    ("5. Talent Concentration", "TC from job postings"),
    ("6. V^R", "vr_score"),
    ("7. Position Factor", "position_factor"),
    ("8. H^R", "hr_score"),
    ("9. Synergy", "synergy_score"),
    ("10. Org-AI-R + CI", "org_air_score, confidence_lower, confidence_upper"),
    ("11. Persist", "Assessment saved to CS1"),
]

for i, (label, desc) in enumerate(STEPS):
    detail = ""
    if result:
        if "V^R" in label:
            detail = f" → **{round(result.get('vr_score', 0), 2)}**"
        elif "Position Factor" in label:
            detail = f" → **{round(result.get('position_factor', 0), 4)}**"
        elif "H^R" in label:
            detail = f" → **{round(result.get('hr_score', 0), 2)}**"
        elif "Synergy" in label:
            detail = f" → **{round(result.get('synergy_score', 0), 2)}**"
        elif "Org-AI-R" in label:
            detail = f" → **{round(result.get('org_air_score', 0), 2)}** (CI: [{round(result.get('confidence_lower', 0), 2)}, {round(result.get('confidence_upper', 0), 2)}])"
    st.write(f"**{label}** — {desc}{detail}")

if not result:
    st.info("Select a company and click **Run Pipeline** to see values in the audit trail.")
