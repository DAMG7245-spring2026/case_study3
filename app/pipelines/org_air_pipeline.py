"""Org-AI-R full scoring pipeline."""

from dataclasses import dataclass, field

from app.scoring.confidence import ConfidenceCalculator
from app.scoring.hr_calculator import HRCalculator
from app.scoring.org_air_calculator import OrgAIRCalculator
from app.scoring.position_factor import PositionFactorCalculator
from app.scoring.synergy_calculator import SynergyCalculator
from app.scoring.talent_concentration import TalentConcentrationCalculator
from app.scoring.vr_calculator import VRCalculator

# ── sector / market-cap helpers ───────────────────────────────────────────────
_SECTOR_MAP: dict[str, str] = {
    "Technology": "technology",
    "Financial": "financial_services",
    "Healthcare": "healthcare",
    "Services": "business_services",
    "Industrials": "manufacturing",
    "Consumer": "retail",
    "Energy": "business_services",
    "Real Estate": "business_services",
}
_MARKET_CAP_PCT: dict[str, float] = {
    "JPM": 0.90,
    "GS": 0.60,
    "WMT": 0.90,
    "TGT": 0.55,
    "UNH": 0.95,
    "HCA": 0.50,
    "CAT": 0.70,
    "DE": 0.65,
    "ADP": 0.80,
    "PAYX": 0.45,
}
_TIMING_FACTOR = 1.05


def _alignment(dim_scores: dict[str, float]) -> float:
    leadership = dim_scores.get("leadership_vision", 50.0)
    governance = dim_scores.get("ai_governance", 50.0)
    raw = (0.6 * leadership + 0.4 * governance) / 100.0
    return max(0.5, min(0.95, raw))


@dataclass
class OrgAIRScores:
    """Plain-data result returned by OrgAIRPipeline.run()."""

    company_id: str
    ticker: str
    company_name: str
    sector: str
    vr_score: float
    hr_score: float
    synergy_score: float
    org_air_score: float
    confidence_lower: float
    confidence_upper: float
    talent_concentration: float
    position_factor: float
    evidence_count: int
    dimension_scores: dict[str, float] = field(default_factory=dict)


class OrgAIRPipeline:
    """Compute the full Org-AI-R score chain for one company."""

    def __init__(self) -> None:
        _ci = ConfidenceCalculator()
        self._tc_calc = TalentConcentrationCalculator()
        self._vr_calc = VRCalculator()
        self._pf_calc = PositionFactorCalculator()
        self._hr_calc = HRCalculator()
        self._syn_calc = SynergyCalculator()
        self._org_calc = OrgAIRCalculator(confidence_calculator=_ci)

    def run(self, company_id: str, db) -> OrgAIRScores:
        """Run VR → PF → HR → Synergy → Org-AI-R and return OrgAIRScores.

        Raises ValueError if company not found.
        Does NOT persist; persistence is the caller's responsibility.
        """
        # Company + industry info
        co = db.execute_one(
            "SELECT id, name, ticker, industry_id FROM companies WHERE id = %s AND is_deleted = FALSE",
            (company_id,),
        )
        if not co:
            raise ValueError(f"Company {company_id} not found")

        industries = {
            r["id"]: r
            for r in db.execute_query(
                "SELECT id, name, sector, h_r_base FROM industries"
            )
        }
        industry_row = industries.get(co["industry_id"], {})
        db_sector = industry_row.get("sector", "Services")
        pf_sector = _SECTOR_MAP.get(db_sector, "business_services")
        h_r_base = float(industry_row.get("h_r_base", 65.0))
        ticker = co["ticker"]
        mcap_pct = _MARKET_CAP_PCT.get(ticker, 0.5)

        # Dimension scores (already computed)
        dim_scores = db.get_dimension_scores(company_id)
        evidence_count = max(1, db.get_evidence_count(company_id))

        # TC from raw job postings
        job_postings = db.get_job_raw_payload(company_id)
        job_analysis = self._tc_calc.analyze_job_postings(job_postings)
        tc = self._tc_calc.calculate_tc(job_analysis)

        # V^R
        vr_result = self._vr_calc.calculate(dim_scores, float(tc))

        # Position Factor
        pf = self._pf_calc.calculate_position_factor(
            vr_score=float(vr_result.vr_score),
            sector=pf_sector,
            market_cap_percentile=mcap_pct,
        )

        # H^R
        hr_result = self._hr_calc.calculate(
            sector=pf_sector,
            position_factor=float(pf),
            baseline_override=h_r_base,
        )

        # Synergy
        syn_result = self._syn_calc.calculate(
            vr_score=vr_result.vr_score,
            hr_score=hr_result.hr_score,
            alignment=_alignment(dim_scores),
            timing_factor=_TIMING_FACTOR,
        )

        # Org-AI-R
        org_result = self._org_calc.calculate(
            company_id=company_id,
            sector=pf_sector,
            vr_result=vr_result,
            hr_result=hr_result,
            synergy_result=syn_result,
            evidence_count=evidence_count,
        )

        return OrgAIRScores(
            company_id=company_id,
            ticker=ticker,
            company_name=co["name"],
            sector=pf_sector,
            vr_score=round(float(vr_result.vr_score), 2),
            hr_score=round(float(hr_result.hr_score), 2),
            synergy_score=round(float(syn_result.synergy_score), 2),
            org_air_score=round(float(org_result.final_score), 2),
            confidence_lower=round(float(org_result.confidence_interval.ci_lower), 2),
            confidence_upper=round(float(org_result.confidence_interval.ci_upper), 2),
            talent_concentration=round(float(tc), 4),
            position_factor=round(float(pf), 4),
            evidence_count=evidence_count,
            dimension_scores={k: round(v, 2) for k, v in dim_scores.items()},
        )
