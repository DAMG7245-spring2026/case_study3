"""Portfolio View: compare up to 5 companies with table and bar charts."""
import json
from uuid import UUID

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from streamlit_ui.components.api_client import get_client, get_companies, get_industries, get_org_air
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
# Industry id -> name for table
try:
    industries_raw = get_industries(client)
    industries_list = industries_raw if isinstance(industries_raw, list) else (industries_raw.get("items") or [])
    industries_by_id = {str(i.get("id", "")): i for i in industries_list if i.get("id")}
except Exception:
    industries_by_id = {}
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
            "sector": None,
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
    ticker = r.get("ticker", "")
    co = ticker_to_company.get(ticker)
    ind_id = co.get("industry_id") if co else None
    industry_name = (industries_by_id.get(str(ind_id), {}).get("name") or "—") if ind_id else "—"
    table_data.append({
        "ticker": ticker,
        "company_name": (r.get("company_name") or "")[:40],
        "Sector": r.get("sector") or "—",
        "Industry": industry_name,
        "Org-AI-R": round(r.get("org_air_score") or 0, 2) if r.get("org_air_score") is not None else "—",
        "V^R": round(r.get("vr_score") or 0, 2) if r.get("vr_score") is not None else "—",
        "H^R": round(r.get("hr_score") or 0, 2) if r.get("hr_score") is not None else "—",
        "Synergy": round(r.get("synergy_score") or 0, 2) if r.get("synergy_score") is not None else "—",
        "TC": round(r.get("talent_concentration") or 0, 4) if r.get("talent_concentration") is not None else "—",
        "PF": round(r.get("position_factor") or 0, 4) if r.get("position_factor") is not None else "—",
    })
st.dataframe(table_data, use_container_width=True, hide_index=True)

# Download portfolio JSON (up to 5 companies)
portfolio_json = json.dumps(portfolio_results, indent=2, default=str)
st.download_button(
    "Download portfolio JSON",
    data=portfolio_json,
    file_name="portfolio.json",
    mime="application/json",
    key="portfolio_download_json",
)

# Charts (Plotly): comparison, sector, heatmaps
valid = [r for r in portfolio_results if r.get("org_air_score") is not None]
if valid:
    tickers = [r.get("ticker", "") for r in valid]
    # 1. Score comparison: Org-AI-R, H^R, V^R by company (grouped bar)
    st.subheader("Score comparison: Org-AI-R, H^R, V^R by company")
    fig = go.Figure(data=[
        go.Bar(name="Org-AI-R", x=tickers, y=[r.get("org_air_score") for r in valid]),
        go.Bar(name="H^R", x=tickers, y=[r.get("hr_score") for r in valid]),
        go.Bar(name="V^R", x=tickers, y=[r.get("vr_score") for r in valid]),
    ])
    fig.update_layout(barmode="group", xaxis_title="Company", yaxis_title="Score", bargap=0.15)
    st.plotly_chart(fig, use_container_width=True)

    # 2. Sector comparison (average scores per sector)
    sector_scores = {}
    for r in valid:
        sec = r.get("sector") or "Unknown"
        if sec not in sector_scores:
            sector_scores[sec] = {"org_air": [], "vr": [], "hr": []}
        sector_scores[sec]["org_air"].append(r.get("org_air_score") or 0)
        sector_scores[sec]["vr"].append(r.get("vr_score") or 0)
        sector_scores[sec]["hr"].append(r.get("hr_score") or 0)
    if sector_scores:
        sectors = list(sector_scores.keys())
        mean_org = [sum(sector_scores[s]["org_air"]) / len(sector_scores[s]["org_air"]) for s in sectors]
        mean_vr = [sum(sector_scores[s]["vr"]) / len(sector_scores[s]["vr"]) for s in sectors]
        mean_hr = [sum(sector_scores[s]["hr"]) / len(sector_scores[s]["hr"]) for s in sectors]
        st.subheader("Sector comparison (average scores)")
        fig_sector = go.Figure(data=[
            go.Bar(name="Org-AI-R", x=sectors, y=mean_org),
            go.Bar(name="V^R", x=sectors, y=mean_vr),
            go.Bar(name="H^R", x=sectors, y=mean_hr),
        ])
        fig_sector.update_layout(barmode="group", xaxis_title="Sector", yaxis_title="Average score", bargap=0.15)
        st.plotly_chart(fig_sector, use_container_width=True)

    # 3. Portfolio score heatmap (companies x Org-AI-R, V^R, H^R, Synergy; 0-100)
    st.subheader("Portfolio score heatmap")
    metric_labels = ["Org-AI-R", "V^R", "H^R", "Synergy"]
    company_labels = [r.get("ticker", "") for r in valid]
    z_scores = []
    for r in valid:
        z_scores.append([
            r.get("org_air_score") or 0,
            r.get("vr_score") or 0,
            r.get("hr_score") or 0,
            r.get("synergy_score") or 0,
        ])
    fig_heatmap = go.Figure(data=go.Heatmap(
        z=z_scores, x=metric_labels, y=company_labels,
        colorscale="RdYlGn", zmin=0, zmax=100, showscale=True,
    ))
    fig_heatmap.update_layout(xaxis_title="Metric", yaxis_title="Company")
    st.plotly_chart(fig_heatmap, use_container_width=True)

    # 4. Dimension scores heatmap (companies x 7 dimensions)
    dim_scores_list = [r.get("dimension_scores") for r in valid]
    if all(dim_scores_list):
        dim_names = sorted(dim_scores_list[0].keys())
        dim_labels = [d.replace("_", " ").title() for d in dim_names]
        z_dim = []
        for r in valid:
            ds = r.get("dimension_scores") or {}
            z_dim.append([round(float(ds.get(d, 0)), 2) for d in dim_names])
        st.subheader("Dimension scores heatmap")
        fig_dim = go.Figure(data=go.Heatmap(
            z=z_dim, x=dim_labels, y=company_labels,
            colorscale="RdYlGn", zmin=0, zmax=100, showscale=True,
        ))
        fig_dim.update_layout(xaxis_title="Dimension", yaxis_title="Company")
        st.plotly_chart(fig_dim, use_container_width=True)

    # --- Additional views (from plan) ---
    st.markdown("---")
    st.subheader("Additional views")

    # 5. Org-AI-R with confidence intervals (error bars)
    st.caption("Org-AI-R with 95% confidence interval")
    org_scores = [r.get("org_air_score") or 0 for r in valid]
    ci_upper = [r.get("confidence_upper") for r in valid]
    ci_lower = [r.get("confidence_lower") for r in valid]
    err_plus = [(ci_upper[i] - org_scores[i]) if ci_upper and ci_upper[i] is not None else 0 for i in range(len(valid))]
    err_minus = [(org_scores[i] - ci_lower[i]) if ci_lower and ci_lower[i] is not None else 0 for i in range(len(valid))]
    fig_ci = go.Figure(data=[go.Bar(
        x=tickers, y=org_scores,
        error_y=dict(type="data", array=err_plus, arrayminus=err_minus),
        name="Org-AI-R",
    )])
    fig_ci.update_layout(xaxis_title="Company", yaxis_title="Org-AI-R score")
    st.plotly_chart(fig_ci, use_container_width=True)

    # 6. V^R vs H^R scatter (balance view)
    st.caption("V^R vs H^R: balance across companies (hover for ticker/sector)")
    hr_vals = [r.get("hr_score") or 0 for r in valid]
    vr_vals = [r.get("vr_score") or 0 for r in valid]
    sectors = [r.get("sector") or "Unknown" for r in valid]
    fig_scatter = go.Figure(data=[go.Scatter(
        x=hr_vals, y=vr_vals, text=tickers, mode="markers+text",
        textposition="top center", marker=dict(size=12),
        hovertemplate="%{text}<br>H^R: %{x:.2f}<br>V^R: %{y:.2f}<extra></extra>",
    )])
    fig_scatter.update_layout(xaxis_title="H^R", yaxis_title="V^R", showlegend=False)
    st.plotly_chart(fig_scatter, use_container_width=True)

    # 7. TC vs PF scatter (risk and position)
    st.caption("Talent concentration vs position factor (risk and sector position)")
    pf_vals = [r.get("position_factor") or 0 for r in valid]
    tc_vals = [r.get("talent_concentration") or 0 for r in valid]
    fig_tc_pf = go.Figure(data=[go.Scatter(
        x=pf_vals, y=tc_vals, text=tickers, mode="markers+text",
        textposition="top center", marker=dict(size=12),
        hovertemplate="%{text}<br>PF: %{x:.2f}<br>TC: %{y:.2f}<extra></extra>",
    )])
    fig_tc_pf.update_layout(xaxis_title="Position factor", yaxis_title="Talent concentration")
    st.plotly_chart(fig_tc_pf, use_container_width=True)

    # 8. Radar (spider) chart for dimensions — one company selector
    if all(dim_scores_list):
        st.caption("Dimension radar: select a company to view 7-dimension shape")
        radar_ticker = st.selectbox("Company for radar", tickers, key="portfolio_radar_ticker")
        r_idx = next((i for i, t in enumerate(tickers) if t == radar_ticker), 0)
        ds = (valid[r_idx].get("dimension_scores") or {})
        dim_order = sorted(ds.keys())
        theta_radar = [d.replace("_", " ").title() for d in dim_order]
        r_radar = [round(float(ds.get(d, 0)), 2) for d in dim_order]
        theta_radar.append(theta_radar[0])
        r_radar.append(r_radar[0])
        fig_radar = go.Figure(data=go.Scatterpolar(r=r_radar, theta=theta_radar, fill="toself", name=radar_ticker))
        fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), showlegend=False)
        st.plotly_chart(fig_radar, use_container_width=True)

    # 9. Ranking / leaderboard bar (Org-AI-R ranked)
    st.caption("Portfolio ranking by Org-AI-R")
    sorted_valid = sorted(valid, key=lambda r: r.get("org_air_score") or 0, reverse=True)
    tickers_sorted = [r.get("ticker", "") for r in sorted_valid]
    scores_sorted = [r.get("org_air_score") or 0 for r in sorted_valid]
    fig_rank = go.Figure(data=[go.Bar(x=scores_sorted, y=tickers_sorted, orientation="h")])
    fig_rank.update_layout(xaxis_title="Org-AI-R score", yaxis_title="Company")
    st.plotly_chart(fig_rank, use_container_width=True)

    # 10. Evidence count vs score (scatter: size = evidence_count)
    st.caption("Org-AI-R vs evidence count (bubble size = evidence count)")
    ev_counts = [r.get("evidence_count") or 0 for r in valid]
    sizes = [max(10, min(50, 15 + (c // 20))) for c in ev_counts]
    fig_ev = go.Figure(data=[go.Scatter(
        x=tickers, y=org_scores, mode="markers",
        marker=dict(size=sizes, sizemode="diameter"),
        text=[f"{t}<br>Org-AI-R: {s:.1f}<br>Evidence: {e}" for t, s, e in zip(tickers, org_scores, ev_counts)],
        hovertemplate="%{text}<extra></extra>",
    )])
    fig_ev.update_layout(xaxis_title="Company", yaxis_title="Org-AI-R score")
    st.plotly_chart(fig_ev, use_container_width=True)

    # 11. Box plot by sector (only if multiple companies per sector)
    sector_counts = {}
    for r in valid:
        sec = r.get("sector") or "Unknown"
        sector_counts[sec] = sector_counts.get(sec, 0) + 1
    if any(c >= 2 for c in sector_counts.values()):
        st.caption("Org-AI-R distribution by sector")
        sector_org = {}
        for r in valid:
            sec = r.get("sector") or "Unknown"
            if sec not in sector_org:
                sector_org[sec] = []
            sector_org[sec].append(r.get("org_air_score") or 0)
        fig_box = go.Figure()
        for sec, vals in sector_org.items():
            fig_box.add_trace(go.Box(y=vals, name=sec))
        fig_box.update_layout(yaxis_title="Org-AI-R score", xaxis_title="Sector")
        st.plotly_chart(fig_box, use_container_width=True)

st.caption("Expected score ranges: N/A (configure in app if needed).")
