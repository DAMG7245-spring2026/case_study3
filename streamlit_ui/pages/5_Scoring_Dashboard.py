"""Scoring Dashboard: score cards, 7-dimension chart, CI, TC, PF."""
import streamlit as st

from streamlit_ui.components.scoring_sidebar import get_last_result, render_scoring_sidebar

st.set_page_config(page_title="Scoring Dashboard | PE Org-AI-R", page_icon="📊", layout="wide")
render_scoring_sidebar()

st.title("Scoring Dashboard")
st.caption("Org-AI-R, V^R, H^R, Synergy, dimension scores, confidence interval, TC and PF")

result = get_last_result()
if not result:
    st.info("Select a company in the sidebar and click **Run Pipeline** to see scores.")
    st.stop()

# Score cards
st.subheader("Score cards")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Org-AI-R", round(result.get("org_air_score", 0), 2))
c2.metric("V^R", round(result.get("vr_score", 0), 2))
c3.metric("H^R", round(result.get("hr_score", 0), 2))
c4.metric("Synergy", round(result.get("synergy_score", 0), 2))

# TC and PF
st.subheader("Talent Concentration & Position Factor")
tc_pf1, tc_pf2 = st.columns(2)
tc_pf1.metric("Talent Concentration", round(result.get("talent_concentration", 0), 4))
tc_pf2.metric("Position Factor", round(result.get("position_factor", 0), 4))

# Confidence interval
st.subheader("Confidence interval")
ci_low = result.get("confidence_lower")
ci_high = result.get("confidence_upper")
if ci_low is not None and ci_high is not None:
    st.write(f"**[{round(ci_low, 2)}, {round(ci_high, 2)}]**")
else:
    st.caption("N/A")

# 7-dimension bar chart
dim_scores = result.get("dimension_scores") or {}
if dim_scores:
    st.subheader("Seven dimensions")
    import pandas as pd
    df = pd.DataFrame(
        [{"dimension": k.replace("_", " ").title(), "score": round(v, 2)} for k, v in dim_scores.items()]
    )
    st.bar_chart(df.set_index("dimension"))
else:
    st.caption("No dimension scores in result.")
