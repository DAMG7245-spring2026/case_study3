"""Company Details: manual HR / V^R / Org-AI-R calculator with form inputs."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from app.models.enums import Dimension
from streamlit_ui.components.api_client import get_company, get_industries, get_org_air
from streamlit_ui.components.scoring_sidebar import (
    KEY_COMPANY_ID,
    KEY_TICKER,
    get_client,
    render_scoring_sidebar,
)

# Sector options for H^R baseline (match hr_calculator built-ins)
SECTOR_OPTIONS = [
    "technology",
    "financial_services",
    "healthcare",
    "business_services",
    "retail",
    "manufacturing",
]
# Map API industry.sector (e.g. "Financial") to SECTOR_OPTIONS value (same as backend _SECTOR_MAP)
SECTOR_MAP = {
    "Technology": "technology",
    "Financial": "financial_services",
    "Healthcare": "healthcare",
    "Services": "business_services",
    "Industrials": "manufacturing",
    "Consumer": "retail",
    "Energy": "business_services",
    "Real Estate": "business_services",
}
DIMENSION_ORDER = list(Dimension)
DEFAULT_DIMENSION_SCORES = "70.0, 75.0, 68.0, 80.0, 72.0, 65.0, 70.0"

# Two-sided z-values for supported confidence levels (no scipy)
_Z_TABLE = {0.80: 1.2816, 0.90: 1.6449, 0.95: 1.9600, 0.99: 2.5758}


def _plot_sem_bell_curve(
    df: pd.DataFrame,
    company_name: str,
    conf_level: float = 0.95,
    picked_date=None,
):
    """Plot a normal-distribution bell curve inferring SEM from a two-sided CI.

    Parameters
    ----------
    df : DataFrame with columns COMPANY_NAME, ASSESSMENT_DATE, V_R_SCORE,
         CONFIDENCE_LOWER, CONFIDENCE_UPPER, and optionally EVIDENCE_COUNT.
    company_name : str — used to filter df and appears in the title.
    conf_level : float — one of 0.80, 0.90, 0.95 (default), 0.99.
    picked_date : optional date/str — selects a specific assessment row;
                  defaults to the latest assessment.

    Reliability interpretation
    --------------------------
    A narrower bell curve (small SEM / tight CI) means more evidence and
    higher confidence in the V^R score. A wider curve signals fewer data
    points and greater uncertainty.

    Returns
    -------
    fig, ax : Matplotlib Figure and Axes.

    Streamlit usage
    ---------------
    fig, ax = _plot_sem_bell_curve(df, company_name)
    st.pyplot(fig)
    """
    z = _Z_TABLE.get(conf_level)
    if z is None:
        raise ValueError(
            f"conf_level must be one of {sorted(_Z_TABLE)}; got {conf_level!r}."
        )

    # Filter to company
    sub = df[df["COMPANY_NAME"] == company_name].copy()
    if sub.empty:
        raise ValueError(f"No rows found for company '{company_name!r}'.")

    # Convert and sort dates
    sub["ASSESSMENT_DATE"] = pd.to_datetime(sub["ASSESSMENT_DATE"])
    sub = sub.sort_values("ASSESSMENT_DATE")

    # Select row
    if picked_date is not None:
        picked_dt = pd.to_datetime(picked_date)
        matches = sub[sub["ASSESSMENT_DATE"] == picked_dt]
        if matches.empty:
            raise ValueError(f"No assessment found for date '{picked_date}'.")
        row = matches.iloc[0]
    else:
        row = sub.iloc[-1]  # latest

    # Validate numeric columns
    for col in ("V_R_SCORE", "CONFIDENCE_LOWER", "CONFIDENCE_UPPER"):
        val = row[col]
        if pd.isna(val):
            raise ValueError(f"Column '{col}' is missing or NaN for the selected row.")
        try:
            float(val)
        except (TypeError, ValueError):
            raise ValueError(f"Column '{col}' must be numeric; got {val!r}.")

    mu = float(row["V_R_SCORE"])
    lower = float(row["CONFIDENCE_LOWER"])
    upper = float(row["CONFIDENCE_UPPER"])
    assessment_date = row["ASSESSMENT_DATE"].date()
    evidence_count = (
        int(row["EVIDENCE_COUNT"])
        if "EVIDENCE_COUNT" in row.index and pd.notna(row["EVIDENCE_COUNT"])
        else None
    )

    if upper <= lower:
        raise ValueError(
            f"CONFIDENCE_UPPER ({upper}) must be strictly greater than "
            f"CONFIDENCE_LOWER ({lower})."
        )

    # Infer SEM from CI half-width
    ci_width = upper - lower
    sem = ci_width / (2.0 * z)

    # Reliability band: narrower CI = higher confidence in V^R score
    if ci_width <= 5:
        reliability_label, reliability_color = "High reliability (narrow CI)", "green"
    elif ci_width <= 15:
        reliability_label, reliability_color = "Moderate reliability", "darkorange"
    else:
        reliability_label, reliability_color = "Low reliability (wide CI)", "red"

    # X grid spanning slightly beyond the CI
    half_width = 0.5 * ci_width
    x_min = max(0.0, lower - half_width)
    x_max = min(100.0, upper + half_width)
    x = np.linspace(x_min, x_max, 600)

    # Normal PDF (NumPy only, no scipy)
    pdf = (1.0 / (sem * np.sqrt(2.0 * np.pi))) * np.exp(-0.5 * ((x - mu) / sem) ** 2)

    # Plot
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(x, pdf, color="steelblue", linewidth=2)
    ax.fill_between(
        x,
        0,
        pdf,
        where=(x >= lower) & (x <= upper),
        color="steelblue",
        alpha=0.2,
        label=f"{int(conf_level * 100)}% CI  [{lower:.2f}, {upper:.2f}]  width={ci_width:.2f}",
    )
    ax.axvline(
        mu,
        linestyle="--",
        color="steelblue",
        linewidth=1.5,
        label=f"Org-AI-R (μ) = {mu:.2f}",
    )
    ax.axvline(
        lower, linestyle=":", color="grey", linewidth=1.2, label=f"Lower = {lower:.2f}"
    )
    ax.axvline(
        upper, linestyle=":", color="grey", linewidth=1.2, label=f"Upper = {upper:.2f}"
    )

    # Evidence count — top left corner, below reliability badge
    ec_text = (
        f"Evidence: {evidence_count} items"
        if evidence_count is not None
        else "Evidence: n/a"
    )
    ax.text(
        0.02,
        0.83,
        ec_text,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=10,
        color="dimgrey",
        bbox=dict(
            boxstyle="round,pad=0.3",
            facecolor="lightyellow",
            edgecolor="grey",
            alpha=0.85,
        ),
    )

    # Reliability badge — top left corner
    ax.text(
        0.02,
        0.97,
        reliability_label,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=10,
        color=reliability_color,
        fontweight="bold",
        bbox=dict(
            boxstyle="round,pad=0.3",
            facecolor="white",
            edgecolor=reliability_color,
            alpha=0.85,
        ),
    )

    ax.set_xlabel("VR Score")
    ax.set_ylabel("Probability Density")
    ax.set_title(
        f"{company_name}  |  {assessment_date}  |  "
        f"{int(conf_level * 100)}% CI  |  SEM = {sem:.3f}",
        fontsize=11,
    )
    ax.legend(fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    return fig, ax


def _alignment_from_dim_scores(dim_scores: dict[str, float]) -> float:
    """Compute alignment from dimension scores (same as backend)."""
    leadership = dim_scores.get("leadership_vision", 50.0)
    governance = dim_scores.get("ai_governance", 50.0)
    raw = (0.6 * leadership + 0.4 * governance) / 100.0
    return max(0.5, min(0.95, raw))


def _sector_and_hr_baseline_from_company(company_id: str):
    """Get sector, hr_baseline, company_name, and industry_name from company + industries APIs."""
    client = get_client()
    try:
        company = get_company(company_id, client=client)
        company_name = company.get("name", "")
        industry_id = company.get("industry_id")
        if not industry_id:
            return ("financial_services", 60.0, company_name, "")
        industries = get_industries(client=client)
        ind = next(
            (i for i in industries if str(i.get("id")) == str(industry_id)), None
        )
        if not ind:
            return ("financial_services", 60.0, company_name, "")
        db_sector = (ind.get("sector") or "Services").strip()
        sector = SECTOR_MAP.get(db_sector, "business_services")
        industry_name = ind.get("name", db_sector)
        return (sector, 60.0, company_name, industry_name)
    except Exception:
        return ("financial_services", 60.0, "", "")
    finally:
        client.close()


def _fetch_prefill_for_company(company_id: str, ticker: str):
    """Fetch org-air for company and return dict of form defaults. Returns None on error."""
    if not company_id or not ticker:
        return None
    client = get_client()
    try:
        data = get_org_air(company_id, client=client)
    except Exception:
        return None
    finally:
        client.close()
    dim_scores = data.get("dimension_scores") or {}
    dim_str = ", ".join(
        str(round(float(dim_scores.get(d.value, 50.0)), 2)) for d in DIMENSION_ORDER
    )
    tc = data.get("talent_concentration")
    tc_pct = (float(tc) * 100.0) if tc is not None else 25.0
    sector = (data.get("sector") or "financial_services").strip()
    sector_index = SECTOR_OPTIONS.index(sector) if sector in SECTOR_OPTIONS else 1
    return {
        "company_label": (
            f"{ticker} ({company_id[:8]}...)"
            if len(company_id) > 8
            else f"{ticker} ({company_id})"
        ),
        "sector": sector,
        "sector_index": sector_index,
        "dim_scores_raw": dim_str or DEFAULT_DIMENSION_SCORES,
        "talent_concentration_pct": round(tc_pct, 2),
        "position_factor": round(float(data.get("position_factor", 0.8)), 2),
        "evidence_count": int(data.get("evidence_count", 15)),
        "alignment": round(_alignment_from_dim_scores(dim_scores), 2),
        "hr_baseline": 60.0,  # not in API response; keep default
    }


def _parse_dimension_scores(raw: str) -> dict[str, float]:
    """Parse comma-separated floats into dimension name -> score (order = Dimension enum)."""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    result = {}
    for i, dim in enumerate(DIMENSION_ORDER):
        if i < len(parts):
            try:
                result[dim.value] = max(0.0, min(100.0, float(parts[i])))
            except ValueError:
                result[dim.value] = 50.0
        else:
            result[dim.value] = 50.0
    return result


st.set_page_config(
    page_title="Org-AI-R Calculator | PE Org-AI-R",
    page_icon="🧮",
    layout="wide",
)
render_scoring_sidebar()

st.title("Company Org-AI-R Scoring Calculator")

# Prefill from selected ticker (GET org-air for that company)
cid = st.session_state.get(KEY_COMPANY_ID, "")
ticker = st.session_state.get(KEY_TICKER, "")

# When the selected company changes, clear form widget state so values update from prefill
_CALC_PREFILL_KEY = "calc_prefill_company_id"
cleared = False
if st.session_state.get(_CALC_PREFILL_KEY) != cid:
    for key in list(st.session_state.keys()):
        if key.startswith("calc_") and key != _CALC_PREFILL_KEY:
            del st.session_state[key]
    st.session_state[_CALC_PREFILL_KEY] = cid
    cleared = True

prefill = _fetch_prefill_for_company(cid, ticker) if cid and ticker else None

# Sector, HR baseline, company name, and industry name: from company + industries
if cid and ticker:
    (
        sector_from_company,
        hr_baseline_from_company,
        company_name_from_db,
        industry_name_from_db,
    ) = _sector_and_hr_baseline_from_company(cid)
else:
    (
        sector_from_company,
        hr_baseline_from_company,
        company_name_from_db,
        industry_name_from_db,
    ) = ("financial_services", 60.0, "", "")

if not (cid and ticker):
    st.info(
        "Select a company (ticker) in the sidebar to prefill the form with that company's scores."
    )
elif prefill is None:
    st.warning(
        "No scoring data for this company yet. Run **Run Pipeline** for this company, or enter values manually."
    )

# Read-only company info panel (upper left, outside the form)
if cid and ticker:
    info_col1, info_col2 = st.columns(2)
    with info_col1:
        display_name = company_name_from_db or ticker
        st.metric(
            "Company", f"{ticker} — {display_name}" if company_name_from_db else ticker
        )
    with info_col2:
        st.metric("Industry Sector", industry_name_from_db or sector_from_company)

# Defaults: from prefill when available, else from company (sector, hr_baseline) or static defaults
default_sector_value = (prefill and prefill.get("sector")) or sector_from_company
if default_sector_value not in SECTOR_OPTIONS:
    default_sector_value = "financial_services"

default_dim_scores = (
    prefill and prefill.get("dim_scores_raw")
) or DEFAULT_DIMENSION_SCORES
default_dim_dict = _parse_dimension_scores(default_dim_scores)
default_tc = (prefill and prefill.get("talent_concentration_pct", 25.0)) or 25.0
default_pf = (prefill and prefill.get("position_factor", 0.80)) or 0.80
default_hr_baseline = (
    prefill and prefill.get("hr_baseline")
) or hr_baseline_from_company
default_align = (prefill and prefill.get("alignment", 0.90)) or 0.90
default_evidence = (prefill and prefill.get("evidence_count", 15)) or 15
default_timing = 1.10

# When company changed: force all form widgets to show prefilled values via session state
if cleared:
    for dim in DIMENSION_ORDER:
        st.session_state[f"calc_dim_{dim.value}"] = default_dim_dict.get(
            dim.value, 50.0
        )
    st.session_state["calc_tc"] = default_tc
    st.session_state["calc_hr_baseline"] = default_hr_baseline
    st.session_state["calc_pf"] = default_pf
    st.session_state["calc_align"] = default_align
    st.session_state["calc_timing"] = default_timing

with st.form("org_air_calculator_form", clear_on_submit=False):
    st.subheader("V^R (Idiosyncratic Readiness) Factors")
    st.caption("Dimension Scores (0–100)")
    dim_cols_a = st.columns(4)
    dim_cols_b = st.columns(3)
    for i, dim in enumerate(DIMENSION_ORDER):
        col = dim_cols_a[i] if i < 4 else dim_cols_b[i - 4]
        with col:
            st.number_input(
                dim.value.replace("_", " ").title(),
                min_value=0.0,
                max_value=100.0,
                value=float(default_dim_dict.get(dim.value, 50.0)),
                step=1.0,
                format="%.1f",
                key=f"calc_dim_{dim.value}",
            )
    talent_concentration_pct = st.number_input(
        "Talent Concentration (%)",
        min_value=0.0,
        max_value=100.0,
        value=default_tc,
        step=1.0,
        format="%.2f",
        help="Stored as ratio 0–1 for V^R (e.g. 25 → 0.25).",
        key="calc_tc",
    )

    st.subheader("H^R (Systematic Opportunity) Factors")
    hr_col1, hr_col2 = st.columns(2)
    with hr_col1:
        hr_baseline = st.number_input(
            "HR Baseline Score (0–100)",
            min_value=0.0,
            max_value=100.0,
            value=default_hr_baseline,
            step=1.0,
            format="%.2f",
            help="Industry baseline; overrides sector default when set.",
            key="calc_hr_baseline",
        )
    with hr_col2:
        position_factor = st.number_input(
            "Position Factor (e.g. −1 to 1)",
            min_value=-1.0,
            max_value=1.0,
            value=default_pf,
            step=0.05,
            format="%.2f",
            help="−1 = laggard, 0 = average, 1 = leader. Used in H^R formula.",
            key="calc_pf",
        )

    st.subheader("Synergy Factors")
    syn_col1, syn_col2 = st.columns(2)
    with syn_col1:
        alignment = st.number_input(
            "Alignment Factor (default 0.8)",
            min_value=0.01,
            max_value=1.0,
            value=default_align,
            step=0.05,
            format="%.2f",
            key="calc_align",
        )
    with syn_col2:
        timing_factor = st.number_input(
            "Timing Factor (default 1.0, clamped [0.8, 1.2])",
            min_value=0.8,
            max_value=1.2,
            value=1.10,
            step=0.05,
            format="%.2f",
            key="calc_timing",
        )

    submitted = st.form_submit_button("Calculate Org-AI-R Score")

if submitted:
    try:
        # Defer scoring imports so page loads without scipy/numpy (avoids env issues)
        from app.scoring.hr_calculator import HRCalculator
        from app.scoring.org_air_calculator import OrgAIRCalculator
        from app.scoring.synergy_calculator import SynergyCalculator
        from app.scoring.vr_calculator import VRCalculator

        dimension_scores = {
            dim.value: float(st.session_state.get(f"calc_dim_{dim.value}", 50.0))
            for dim in DIMENSION_ORDER
        }
        talent_concentration_pct = st.session_state.get("calc_tc", 25.0)
        talent_concentration = talent_concentration_pct / 100.0

        vr_calc = VRCalculator()
        vr_result = vr_calc.calculate(dimension_scores, talent_concentration)

        sector = sector_from_company
        hr_baseline = st.session_state.get("calc_hr_baseline", 60.0)
        position_factor = st.session_state.get("calc_pf", 0.80)
        hr_calc = HRCalculator()
        hr_result = hr_calc.calculate(
            sector,
            position_factor,
            baseline_override=hr_baseline if hr_baseline else None,
        )

        alignment = st.session_state.get("calc_align", 0.9)
        timing_factor = st.session_state.get("calc_timing", 1.1)
        syn_calc = SynergyCalculator()
        syn_result = syn_calc.calculate(
            vr_result.vr_score,
            hr_result.hr_score,
            alignment,
            timing_factor,
        )

        company_id = cid or "ACME_CORP"
        evidence_count = default_evidence
        confidence_level = 0.95
        org_calc = OrgAIRCalculator()
        org_result = org_calc.calculate(
            company_id=company_id or "ACME_CORP",
            sector=sector,
            vr_result=vr_result,
            hr_result=hr_result,
            synergy_result=syn_result,
            evidence_count=int(evidence_count),
            confidence_level=float(confidence_level),
        )

        st.success("Org-AI-R score calculated.")

        # Prominent Org-AI-R score
        org_score = round(float(org_result.final_score), 2)
        st.subheader(f"Org-AI-R Score")
        st.markdown(
            f"<h1 style='margin-top:0'>{org_score}</h1>", unsafe_allow_html=True
        )

        # Supporting factors on next line
        f1, f2, f3 = st.columns(3)
        f1.metric(
            "V^R (Idiosyncratic Readiness)",
            round(float(org_result.vr_result.vr_score), 2),
        )
        f2.metric(
            "H^R (Systematic Opportunity)",
            round(float(org_result.hr_result.hr_score), 2),
        )
        f3.metric("Synergy", round(float(org_result.synergy_result.synergy_score), 2))

        # SEM bell-curve graph
        st.subheader("SEM Confidence Interval")
        _display_name = company_name_from_db or ticker or "Company"
        _bell_df = pd.DataFrame(
            [
                {
                    "COMPANY_NAME": _display_name,
                    "ASSESSMENT_DATE": pd.Timestamp.today().normalize(),
                    "V_R_SCORE": float(org_result.final_score),
                    "CONFIDENCE_LOWER": float(org_result.confidence_interval.ci_lower),
                    "CONFIDENCE_UPPER": float(org_result.confidence_interval.ci_upper),
                    "EVIDENCE_COUNT": int(
                        org_result.confidence_interval.evidence_count
                    ),
                }
            ]
        )
        try:
            _fig, _ = _plot_sem_bell_curve(_bell_df, _display_name, conf_level=0.95)
            st.pyplot(_fig)
            plt.close(_fig)
        except ValueError as _bell_err:
            st.warning(f"Bell curve could not be rendered: {_bell_err}")
    except ImportError as e:
        st.error(
            "Scoring engine could not be loaded (numpy/scipy). "
            "Try: `poetry run pip install --upgrade numpy scipy` or use Python 3.11/3.12."
        )
        st.exception(e)
    except Exception as e:
        st.error(f"Calculation failed: {e}")
        st.exception(e)
