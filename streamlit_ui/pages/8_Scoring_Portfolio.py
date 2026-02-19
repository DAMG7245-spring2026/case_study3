"""Portfolio View: compare up to 5 companies with table and bar charts."""
from uuid import UUID

import streamlit as st

from streamlit_ui.components.api_client import get_client, get_companies, get_org_air
from streamlit_ui.components.scoring_sidebar import render_scoring_sidebar

st.set_page_config(page_title="Portfolio View | PE Org-AI-R", page_icon="📈", layout="wide")
render_scoring_sidebar()

st.title("Portfolio View")
st.caption("Compare up to 5 companies (NVDA, JPM, WMT, GE, DG or any available)")

# Default suggested tickers; use only those that exist in DB
SUGGESTED = ["NVDA", "JPM", "WMT", "GE", "DG"]
client = get_client()
try:
    data = get_companies(client, page=1, page_size=100)
except Exception:
    st.error("Could not load companies.")
    client.close()
    st.stop()

items = data.get("items") or []
tickers_available = [str(c.get("ticker", "")) for c in items if c.get("ticker")]
ticker_to_company = {str(c.get("ticker", "")): c for c in items if c.get("ticker")}
# Limit to 5
selected_tickers = st.multiselect(
    "Select up to 5 companies",
    options=tickers_available,
    default=[t for t in SUGGESTED if t in tickers_available][:5],
    key="portfolio_tickers",
)
if len(selected_tickers) > 5:
    selected_tickers = selected_tickers[:5]
    st.warning("Only first 5 companies shown.")

if not selected_tickers:
    st.info("Select at least one company.")
    client.close()
    st.stop()

# Fetch Org-AI-R for each
portfolio_results = []
for ticker in selected_tickers:
    co = ticker_to_company.get(ticker)
    if not co:
        continue
    cid = co.get("id")
    try:
        org = get_org_air(cid, client=client)
        portfolio_results.append(org)
    except Exception:
        portfolio_results.append({
            "ticker": ticker,
            "company_name": co.get("name", ticker),
            "org_air_score": None,
            "vr_score": None,
            "hr_score": None,
            "synergy_score": None,
            "talent_concentration": None,
            "position_factor": None,
        })

client.close()

if not portfolio_results:
    st.warning("No results for selected companies.")
    st.stop()

# Table
st.subheader("Comparison table")
table_data = []
for r in portfolio_results:
    table_data.append({
        "ticker": r.get("ticker", ""),
        "company_name": (r.get("company_name") or "")[:40],
        "Org-AI-R": round(r.get("org_air_score") or 0, 2) if r.get("org_air_score") is not None else "—",
        "V^R": round(r.get("vr_score") or 0, 2) if r.get("vr_score") is not None else "—",
        "H^R": round(r.get("hr_score") or 0, 2) if r.get("hr_score") is not None else "—",
        "Synergy": round(r.get("synergy_score") or 0, 2) if r.get("synergy_score") is not None else "—",
        "TC": round(r.get("talent_concentration") or 0, 4) if r.get("talent_concentration") is not None else "—",
        "PF": round(r.get("position_factor") or 0, 4) if r.get("position_factor") is not None else "—",
    })
st.dataframe(table_data, use_container_width=True, hide_index=True)

# Bar charts (numeric only)
import pandas as pd
valid = [r for r in portfolio_results if r.get("org_air_score") is not None]
if valid:
    df_org = pd.DataFrame([{"company": r.get("ticker", ""), "Org-AI-R": r.get("org_air_score")} for r in valid])
    st.subheader("Org-AI-R by company")
    st.bar_chart(df_org.set_index("company"))
    df_vr = pd.DataFrame([{"company": r.get("ticker", ""), "V^R": r.get("vr_score")} for r in valid])
    st.subheader("V^R by company")
    st.bar_chart(df_vr.set_index("company"))

st.caption("Expected score ranges: N/A (configure in app if needed).")
