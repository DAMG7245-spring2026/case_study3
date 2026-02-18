"""Dimension score endpoints + full Org-AI-R scoring pipeline endpoints."""
import json
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel
from app.models import DimensionScoreUpdate, DimensionScoreResponse
from app.models.enums import Dimension
from app.pipelines.dimension_scorer import DimensionScoringPipeline
from app.scoring.confidence import ConfidenceCalculator
from app.scoring.hr_calculator import HRCalculator
from app.scoring.org_air_calculator import OrgAIRCalculator
from app.scoring.position_factor import PositionFactorCalculator
from app.scoring.synergy_calculator import SynergyCalculator
from app.scoring.talent_concentration import TalentConcentrationCalculator
from app.scoring.vr_calculator import VRCalculator
from app.services import get_snowflake_service, get_redis_cache, CacheKeys

# ── sector / market-cap helpers (same as scripts/compute_scores.py) ───────────
_SECTOR_MAP: dict[str, str] = {
    "Technology":  "technology",
    "Financial":   "financial_services",
    "Healthcare":  "healthcare",
    "Services":    "business_services",
    "Industrials": "manufacturing",
    "Consumer":    "retail",
    "Energy":      "business_services",
    "Real Estate": "business_services",
}
_MARKET_CAP_PCT: dict[str, float] = {
    "JPM": 0.90, "GS": 0.60, "WMT": 0.90, "TGT": 0.55,
    "UNH": 0.95, "HCA": 0.50, "CAT": 0.70, "DE":  0.65,
    "ADP": 0.80, "PAYX": 0.45,
}
_TIMING_FACTOR = 1.05


def _alignment(dim_scores: dict[str, float]) -> float:
    leadership = dim_scores.get("leadership_vision", 50.0)
    governance  = dim_scores.get("ai_governance",   50.0)
    raw = (0.6 * leadership + 0.4 * governance) / 100.0
    return max(0.5, min(0.95, raw))


# ── response schema ───────────────────────────────────────────────────────────

class OrgAIRResponse(BaseModel):
    """Full Org-AI-R result for one company."""
    company_id:           UUID
    ticker:               str
    company_name:         str
    sector:               str
    vr_score:             float
    hr_score:             float
    synergy_score:        float
    org_air_score:        float
    confidence_lower:     float
    confidence_upper:     float
    talent_concentration: float
    position_factor:      float
    evidence_count:       int
    dimension_scores:     dict[str, float]

router = APIRouter(prefix="/api/v1/scores", tags=["Dimension Scores"])


@router.put(
    "/{score_id}",
    response_model=DimensionScoreResponse,
    summary="Update Dimension Score"
)
async def update_dimension_score(score_id: UUID, update: DimensionScoreUpdate):
    """Update a dimension score."""
    db = get_snowflake_service()
    cache = get_redis_cache()
    
    # Get existing score
    row = db.execute_one(
        """
        SELECT id, company_id, dimension, score, total_weight, confidence, evidence_count, contributing_sources, created_at
        FROM dimension_scores WHERE id = %s
        """,
        (str(score_id),)
    )
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dimension score {score_id} not found"
        )
    
    # Build update query
    updates = []
    params = []
    update_data = update.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        if value is not None:
            updates.append(f"{field} = %s")
            params.append(value)
    
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    params.append(str(score_id))
    
    db.execute_write(
        f"UPDATE dimension_scores SET {', '.join(updates)} WHERE id = %s",
        tuple(params)
    )
    
    # Invalidate company cache
    cache.delete(CacheKeys.company(row["company_id"]))
    
    # Fetch and return updated score
    updated_row = db.execute_one(
        """
        SELECT id, company_id, dimension, score, total_weight, confidence, evidence_count, contributing_sources, created_at
        FROM dimension_scores WHERE id = %s
        """,
        (str(score_id),)
    )

    sources = updated_row["contributing_sources"]
    if isinstance(sources, str):
        sources = json.loads(sources)

    return DimensionScoreResponse(
        id=UUID(updated_row["id"]),
        company_id=UUID(updated_row["company_id"]),
        dimension=Dimension(updated_row["dimension"]),
        score=float(updated_row["score"]),
        total_weight=float(updated_row["total_weight"]) if updated_row["total_weight"] else None,
        confidence=float(updated_row["confidence"]),
        evidence_count=updated_row["evidence_count"],
        contributing_sources=sources,
        created_at=updated_row["created_at"]
    )


@router.post(
    "/companies/{company_id}/compute-dimension-scores",
    response_model=list[DimensionScoreResponse],
    summary="Compute and Store Dimension Scores",
)
async def compute_dimension_scores(company_id: UUID):
    """Run the dimension scoring pipeline for a company.

    Fetches aggregated external signals and SEC document chunks, scores them
    through the EvidenceMapper + RubricScorer, then upserts all 7 dimension
    scores to Snowflake.
    """
    db = get_snowflake_service()
    cache = get_redis_cache()

    # Verify company exists
    company = db.execute_one(
        "SELECT id FROM companies WHERE id = %s AND is_deleted = FALSE",
        (str(company_id),),
    )
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found",
        )

    pipeline = DimensionScoringPipeline(db)
    pipeline.compute_and_store(str(company_id))

    # Invalidate company cache
    cache.delete(CacheKeys.company(str(company_id)))

    # Return freshly persisted scores
    rows = db.execute_query(
        """
        SELECT id, company_id, dimension, score, total_weight, confidence,
               evidence_count, contributing_sources, created_at
        FROM dimension_scores
        WHERE company_id = %s
        ORDER BY dimension
        """,
        (str(company_id),),
    )

    def _parse_sources(val) -> list:
        if isinstance(val, str):
            return json.loads(val)
        return val or []

    return [
        DimensionScoreResponse(
            id=UUID(r["id"]),
            company_id=UUID(r["company_id"]),
            dimension=Dimension(r["dimension"]),
            score=float(r["score"]),
            total_weight=float(r["total_weight"]) if r["total_weight"] else None,
            confidence=float(r["confidence"]),
            evidence_count=r["evidence_count"],
            contributing_sources=_parse_sources(r["contributing_sources"]),
            created_at=r["created_at"],
        )
        for r in rows
    ]


# ── shared calculators (module-level singletons) ──────────────────────────────
_tc_calc   = TalentConcentrationCalculator()
_vr_calc   = VRCalculator()
_pf_calc   = PositionFactorCalculator()
_hr_calc   = HRCalculator()
_syn_calc  = SynergyCalculator()
_ci_calc   = ConfidenceCalculator()
_org_calc  = OrgAIRCalculator(confidence_calculator=_ci_calc)


def _run_org_air_for_company(company_id: str, db) -> OrgAIRResponse:
    """Core scoring logic shared by compute and GET endpoints."""
    # Company + industry info
    co = db.execute_one(
        "SELECT id, name, ticker, industry_id FROM companies WHERE id = %s AND is_deleted = FALSE",
        (company_id,),
    )
    if not co:
        raise HTTPException(status_code=404, detail=f"Company {company_id} not found")

    industries = {
        r["id"]: r
        for r in db.execute_query("SELECT id, name, sector, h_r_base FROM industries")
    }
    industry_row = industries.get(co["industry_id"], {})
    db_sector   = industry_row.get("sector", "Services")
    pf_sector   = _SECTOR_MAP.get(db_sector, "business_services")
    h_r_base    = float(industry_row.get("h_r_base", 65.0))
    ticker      = co["ticker"]
    mcap_pct    = _MARKET_CAP_PCT.get(ticker, 0.5)

    # Dimension scores (already computed)
    dim_scores    = db.get_dimension_scores(company_id)
    evidence_count = max(1, db.get_evidence_count(company_id))

    # TC from raw job postings
    job_postings = db.get_job_raw_payload(company_id)
    job_analysis = _tc_calc.analyze_job_postings(job_postings)
    tc           = _tc_calc.calculate_tc(job_analysis)

    # V^R
    vr_result = _vr_calc.calculate(dim_scores, float(tc))

    # Position Factor
    pf = _pf_calc.calculate_position_factor(
        vr_score=float(vr_result.vr_score),
        sector=pf_sector,
        market_cap_percentile=mcap_pct,
    )

    # H^R
    hr_result = _hr_calc.calculate(
        sector=pf_sector,
        position_factor=float(pf),
        baseline_override=h_r_base,
    )

    # Synergy
    syn_result = _syn_calc.calculate(
        vr_score=vr_result.vr_score,
        hr_score=hr_result.hr_score,
        alignment=_alignment(dim_scores),
        timing_factor=_TIMING_FACTOR,
    )

    # Org-AI-R
    org_result = _org_calc.calculate(
        company_id=company_id,
        sector=pf_sector,
        vr_result=vr_result,
        hr_result=hr_result,
        synergy_result=syn_result,
        evidence_count=evidence_count,
    )

    return OrgAIRResponse(
        company_id=UUID(company_id),
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
    ), org_result, float(pf), float(tc)


@router.post(
    "/companies/{company_id}/compute-org-air",
    response_model=OrgAIRResponse,
    summary="Compute Full Org-AI-R Score",
    tags=["Org-AI-R Scoring"],
)
async def compute_org_air(company_id: UUID):
    """Run the full Org-AI-R pipeline for a company.

    Steps:
    1. Recompute 7 dimension scores (DimensionScoringPipeline)
    2. Compute Talent Concentration from raw job postings
    3. Compute V^R → Position Factor → H^R → Synergy → Org-AI-R + CI
    4. Upsert results into the assessments table

    Returns the complete scoring result.
    """
    db    = get_snowflake_service()
    cache = get_redis_cache()
    cid   = str(company_id)

    # Step 1 – recompute dimension scores
    pipeline = DimensionScoringPipeline(db)
    try:
        pipeline.compute_and_store(cid)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Dimension scoring failed: {exc}")

    # Steps 2-8
    response, org_result, pf, tc = _run_org_air_for_company(cid, db)

    # Step 9 – persist
    db.upsert_assessment(
        company_id=cid,
        v_r_score=response.vr_score,
        h_r_score=response.hr_score,
        synergy=response.synergy_score,
        org_air_score=response.org_air_score,
        confidence_lower=response.confidence_lower,
        confidence_upper=response.confidence_upper,
        position_factor=pf,
        talent_concentration=tc,
    )

    # Invalidate caches
    cache.delete(CacheKeys.company(cid))

    return response


@router.get(
    "/companies/{company_id}/org-air",
    response_model=OrgAIRResponse,
    summary="Get Org-AI-R Score",
    tags=["Org-AI-R Scoring"],
)
async def get_org_air(company_id: UUID):
    """Return the current Org-AI-R scores for a company.

    Reads dimension scores already in the DB (does NOT re-run the pipeline)
    and recomputes the scoring chain to return a fresh result.
    Use POST compute-org-air to also re-run dimension scoring.
    """
    db  = get_snowflake_service()
    cid = str(company_id)
    response, _, _, _ = _run_org_air_for_company(cid, db)
    return response


@router.get(
    "/org-air",
    response_model=list[OrgAIRResponse],
    summary="Get Org-AI-R Scores for All Companies",
    tags=["Org-AI-R Scoring"],
)
async def list_org_air(ticker: Optional[str] = None):
    """Return Org-AI-R scores for all (or a filtered) set of companies.

    Query param:
    - **ticker**: optional comma-separated list, e.g. `?ticker=JPM,WMT`
    """
    db = get_snowflake_service()
    companies = db.execute_query(
        "SELECT id, name, ticker FROM companies WHERE is_deleted = FALSE ORDER BY name"
    )
    if ticker:
        wanted = {t.strip().upper() for t in ticker.split(",")}
        companies = [c for c in companies if c["ticker"] in wanted]

    results = []
    for co in companies:
        try:
            resp, _, _, _ = _run_org_air_for_company(str(co["id"]), db)
            results.append(resp)
        except Exception:
            continue  # skip companies with insufficient data

    return results