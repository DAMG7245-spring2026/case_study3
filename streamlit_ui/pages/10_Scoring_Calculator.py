"""Company Details: manual HR / V^R / Org-AI-R calculator with form inputs."""
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


def _alignment_from_dim_scores(dim_scores: dict[str, float]) -> float:
    """Compute alignment from dimension scores (same as backend)."""
    leadership = dim_scores.get("leadership_vision", 50.0)
    governance = dim_scores.get("ai_governance", 50.0)
    raw = (0.6 * leadership + 0.4 * governance) / 100.0
    return max(0.5, min(0.95, raw))


def _sector_and_hr_baseline_from_company(company_id: str):
    """Get sector (SECTOR_OPTIONS value) from company + industries APIs. HR baseline defaults to 60 (API does not expose h_r_base)."""
    client = get_client()
    try:
        company = get_company(company_id, client=client)
        industry_id = company.get("industry_id")
        if not industry_id:
            return ("financial_services", 60.0)
        industries = get_industries(client=client)
        ind = next((i for i in industries if str(i.get("id")) == str(industry_id)), None)
        if not ind:
            return ("financial_services", 60.0)
        db_sector = (ind.get("sector") or "Services").strip()
        sector = SECTOR_MAP.get(db_sector, "business_services")
        return (sector, 60.0)
    except Exception:
        return ("financial_services", 60.0)
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
        "company_label": f"{ticker} ({company_id[:8]}...)" if len(company_id) > 8 else f"{ticker} ({company_id})",
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

st.title("Company Details")
st.caption("Enter factors to calculate Org-AI-R (V^R, H^R, Synergy, CI). Values prefill from the company selected in the sidebar.")

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

# Sector and HR baseline: from prefill when available, else from company + industries
if cid and ticker:
    sector_from_company, hr_baseline_from_company = _sector_and_hr_baseline_from_company(cid)
else:
    sector_from_company, hr_baseline_from_company = "financial_services", 60.0

if not (cid and ticker):
    st.info("Select a company (ticker) in the sidebar to prefill the form with that company's scores.")
elif prefill is None:
    st.warning("No scoring data for this company yet. Run **Run Pipeline** for this company, or enter values manually.")

# Company label: always show selected ticker + id when a company is selected
if cid and ticker:
    default_company_label = f"{ticker} ({cid[:8]}...)" if len(cid) > 8 else f"{ticker} ({cid})"
else:
    default_company_label = "ACME_CORP"

# Defaults: from prefill when available, else from company (sector, hr_baseline) or static defaults
default_sector_value = (prefill and prefill.get("sector")) or sector_from_company
if default_sector_value not in SECTOR_OPTIONS:
    default_sector_value = "financial_services"
default_sector_index = SECTOR_OPTIONS.index(default_sector_value)

default_dim_scores = (prefill and prefill.get("dim_scores_raw")) or DEFAULT_DIMENSION_SCORES
default_tc = (prefill and prefill.get("talent_concentration_pct", 25.0)) or 25.0
default_pf = (prefill and prefill.get("position_factor", 0.80)) or 0.80
default_hr_baseline = (prefill and prefill.get("hr_baseline")) or hr_baseline_from_company
default_align = (prefill and prefill.get("alignment", 0.90)) or 0.90
default_evidence = (prefill and prefill.get("evidence_count", 15)) or 15
default_timing = 1.10
default_cl = 0.95
default_tier = 2

# When company changed: force all form widgets to show prefilled values via session state
# Company ID always reflects current sidebar selection
st.session_state["calc_company_id"] = default_company_label
if cleared:
    st.session_state["calc_sector"] = default_sector_value
    st.session_state["calc_dim_scores"] = default_dim_scores
    st.session_state["calc_tc"] = default_tc
    st.session_state["calc_hr_baseline"] = default_hr_baseline
    st.session_state["calc_pf"] = default_pf
    st.session_state["calc_align"] = default_align
    st.session_state["calc_timing"] = default_timing
    st.session_state["calc_evidence_count"] = default_evidence
    st.session_state["calc_tier"] = default_tier
    st.session_state["calc_cl"] = default_cl

with st.form("org_air_calculator_form", clear_on_submit=False):
    st.subheader("Company Details")
    col_cid, col_sec = st.columns(2)
    with col_cid:
        company_id = st.text_input(
            "Company ID",
            value=default_company_label,
            help="Display only; reflects company selected in the sidebar.",
            key="calc_company_id",
            disabled=True,
        )
    with col_sec:
        sector = st.selectbox(
            "Sector ID",
            options=SECTOR_OPTIONS,
            index=min(default_sector_index, len(SECTOR_OPTIONS) - 1),
            help="Used for H^R baseline when not overridden.",
            key="calc_sector",
        )

    st.subheader("V^R (Idiosyncratic Readiness) Factors")
    dim_scores_raw = st.text_input(
        "Dimension Scores (comma-separated floats, 0–100)",
        value=default_dim_scores,
        help="Seven scores in order: Data, Gov, Tech, Talent, Lead, Use, Culture. Missing/default 50.",
        key="calc_dim_scores",
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

    st.subheader("Confidence Interval Factors")
    ci_col1, ci_col2, ci_col3 = st.columns(3)
    with ci_col1:
        evidence_count = st.number_input(
            "Evidence Count (for CI calculation, default 10)",
            min_value=1,
            value=default_evidence,
            step=1,
            key="calc_evidence_count",
        )
    with ci_col2:
        confidence_tier = st.number_input(
            "Confidence Tier (default 2, currently not used in SEM logic)",
            min_value=0,
            value=2,
            step=1,
            key="calc_tier",
        )
    with ci_col3:
        confidence_level = st.number_input(
            "Confidence Level (e.g. 0.95 for 95% CI)",
            min_value=0.5,
            max_value=0.99,
            value=0.95,
            step=0.01,
            format="%.2f",
            key="calc_cl",
        )

    submitted = st.form_submit_button("Calculate Org-AI-R Score")

if submitted:
    try:
        # Defer scoring imports so page loads without scipy/numpy (avoids env issues)
        from app.scoring.hr_calculator import HRCalculator
        from app.scoring.org_air_calculator import OrgAIRCalculator
        from app.scoring.synergy_calculator import SynergyCalculator
        from app.scoring.vr_calculator import VRCalculator

        dim_scores_raw = st.session_state.get("calc_dim_scores", DEFAULT_DIMENSION_SCORES)
        dimension_scores = _parse_dimension_scores(dim_scores_raw)
        talent_concentration_pct = st.session_state.get("calc_tc", 25.0)
        talent_concentration = talent_concentration_pct / 100.0

        vr_calc = VRCalculator()
        vr_result = vr_calc.calculate(dimension_scores, talent_concentration)

        sector = st.session_state.get("calc_sector", "financial_services")
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

        company_id = st.session_state.get("calc_company_id", "ACME_CORP")
        evidence_count = st.session_state.get("calc_evidence_count", 15)
        confidence_level = st.session_state.get("calc_cl", 0.95)
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
        st.subheader("Results")

        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Org-AI-R", round(float(org_result.final_score), 2))
        r2.metric("V^R", round(float(org_result.vr_result.vr_score), 2))
        r3.metric("H^R", round(float(org_result.hr_result.hr_score), 2))
        r4.metric("Synergy", round(float(org_result.synergy_result.synergy_score), 2))

        st.subheader("Confidence interval")
        ci = org_result.confidence_interval
        st.write(
            f"**[{round(float(ci.ci_lower), 2)}, {round(float(ci.ci_upper), 2)}]** "
            f"(SEM: {round(float(ci.sem), 2)}, evidence_count: {ci.evidence_count})"
        )

        with st.expander("Full result (JSON)"):
            st.json(org_result.to_dict())
    except ImportError as e:
        st.error(
            "Scoring engine could not be loaded (numpy/scipy). "
            "Try: `poetry run pip install --upgrade numpy scipy` or use Python 3.11/3.12."
        )
        st.exception(e)
    except Exception as e:
        st.error(f"Calculation failed: {e}")
        st.exception(e)
