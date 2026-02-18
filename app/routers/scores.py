"""Dimension score endpoints + Org-AI-R scoring endpoints."""

import json
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.models import DimensionScoreUpdate, DimensionScoreResponse
from app.models.enums import Dimension
from app.pipelines.dimension_scorer import DimensionScoringPipeline
from app.pipelines.org_air_pipeline import OrgAIRPipeline, OrgAIRScores
from app.services import get_snowflake_service, get_redis_cache, CacheKeys

# ── response schema ───────────────────────────────────────────────────────────


class OrgAIRResponse(BaseModel):
    """Full Org-AI-R result for one company."""

    company_id: UUID
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
    dimension_scores: dict[str, float]


class ComputeScoresResponse(BaseModel):
    """Combined result: full dimension score list + Org-AI-R."""

    dimension_scores: list[DimensionScoreResponse]
    org_air: OrgAIRResponse


def _to_response(scores: OrgAIRScores) -> OrgAIRResponse:
    return OrgAIRResponse(
        company_id=UUID(scores.company_id),
        ticker=scores.ticker,
        company_name=scores.company_name,
        sector=scores.sector,
        vr_score=scores.vr_score,
        hr_score=scores.hr_score,
        synergy_score=scores.synergy_score,
        org_air_score=scores.org_air_score,
        confidence_lower=scores.confidence_lower,
        confidence_upper=scores.confidence_upper,
        talent_concentration=scores.talent_concentration,
        position_factor=scores.position_factor,
        evidence_count=scores.evidence_count,
        dimension_scores=scores.dimension_scores,
    )


router = APIRouter(prefix="/api/v1/scores")


@router.put(
    "/{score_id}",
    response_model=DimensionScoreResponse,
    summary="Update Dimension Score",
    tags=["Dimension Scores"],
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
        (str(score_id),),
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dimension score {score_id} not found",
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
            status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update"
        )

    params.append(str(score_id))

    db.execute_write(
        f"UPDATE dimension_scores SET {', '.join(updates)} WHERE id = %s", tuple(params)
    )

    # Invalidate company cache
    cache.delete(CacheKeys.company(row["company_id"]))

    # Fetch and return updated score
    updated_row = db.execute_one(
        """
        SELECT id, company_id, dimension, score, total_weight, confidence, evidence_count, contributing_sources, created_at
        FROM dimension_scores WHERE id = %s
        """,
        (str(score_id),),
    )

    sources = updated_row["contributing_sources"]
    if isinstance(sources, str):
        sources = json.loads(sources)

    return DimensionScoreResponse(
        id=UUID(updated_row["id"]),
        company_id=UUID(updated_row["company_id"]),
        dimension=Dimension(updated_row["dimension"]),
        score=float(updated_row["score"]),
        total_weight=(
            float(updated_row["total_weight"]) if updated_row["total_weight"] else None
        ),
        confidence=float(updated_row["confidence"]),
        evidence_count=updated_row["evidence_count"],
        contributing_sources=sources,
        created_at=updated_row["created_at"],
    )


@router.post(
    "/companies/{company_id}/compute-dimension-scores",
    response_model=list[DimensionScoreResponse],
    summary="Compute and Store Dimension Scores",
    tags=["Dimension Scores"],
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
    db = get_snowflake_service()
    cache = get_redis_cache()
    cid = str(company_id)

    # Step 1 – recompute dimension scores
    dim_pipeline = DimensionScoringPipeline(db)
    try:
        dim_pipeline.compute_and_store(cid)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Dimension scoring failed: {exc}")

    # Steps 2-8
    try:
        scores = OrgAIRPipeline().run(cid, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    # Step 9 – persist
    db.upsert_assessment(
        company_id=cid,
        v_r_score=scores.vr_score,
        h_r_score=scores.hr_score,
        synergy=scores.synergy_score,
        org_air_score=scores.org_air_score,
        confidence_lower=scores.confidence_lower,
        confidence_upper=scores.confidence_upper,
        position_factor=scores.position_factor,
        talent_concentration=scores.talent_concentration,
    )

    # Invalidate caches
    cache.delete(CacheKeys.company(cid))

    return _to_response(scores)


@router.post(
    "/companies/{company_id}/score-company",
    response_model=ComputeScoresResponse,
    summary="Compute Dimension Scores + Org-AI-R (combined)",
    tags=["Org-AI-R Scoring"],
)
async def compute_all(company_id: UUID):
    """Run both pipelines in one call and return the combined result.

    Steps:
    1. Compute and store all 7 dimension scores (DimensionScoringPipeline).
    2. Compute V^R → Position Factor → H^R → Synergy → Org-AI-R + CI (OrgAIRPipeline).
    3. Persist the assessment to Snowflake.
    4. Invalidate the company cache.

    Returns `dimension_scores` (detailed per-dimension list) and `org_air`
    (full Org-AI-R result) in a single response.
    """
    db = get_snowflake_service()
    cache = get_redis_cache()
    cid = str(company_id)

    # Verify company exists
    company = db.execute_one(
        "SELECT id FROM companies WHERE id = %s AND is_deleted = FALSE",
        (cid,),
    )
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found",
        )

    # Step 1 – dimension scores
    try:
        DimensionScoringPipeline(db).compute_and_store(cid)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Dimension scoring failed: {exc}")

    # Step 2 – full Org-AI-R pipeline
    try:
        scores = OrgAIRPipeline().run(cid, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    # Step 3 – persist assessment
    db.upsert_assessment(
        company_id=cid,
        v_r_score=scores.vr_score,
        h_r_score=scores.hr_score,
        synergy=scores.synergy_score,
        org_air_score=scores.org_air_score,
        confidence_lower=scores.confidence_lower,
        confidence_upper=scores.confidence_upper,
        position_factor=scores.position_factor,
        talent_concentration=scores.talent_concentration,
    )

    # Invalidate cache
    cache.delete(CacheKeys.company(cid))

    # Fetch freshly persisted dimension score rows
    rows = db.execute_query(
        """
        SELECT id, company_id, dimension, score, total_weight, confidence,
               evidence_count, contributing_sources, created_at
        FROM dimension_scores
        WHERE company_id = %s
        ORDER BY dimension
        """,
        (cid,),
    )

    def _parse_sources(val) -> list:
        if isinstance(val, str):
            return json.loads(val)
        return val or []

    dim_responses = [
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

    return ComputeScoresResponse(
        dimension_scores=dim_responses,
        org_air=_to_response(scores),
    )


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
    db = get_snowflake_service()
    cid = str(company_id)
    try:
        scores = OrgAIRPipeline().run(cid, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _to_response(scores)


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

    pipeline = OrgAIRPipeline()
    results = []
    for co in companies:
        try:
            scores = pipeline.run(str(co["id"]), db)
            results.append(_to_response(scores))
        except Exception:
            continue  # skip companies with insufficient data

    return results
