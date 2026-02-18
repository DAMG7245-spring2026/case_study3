"""Dimension score endpoints."""
import json
from uuid import UUID
from fastapi import APIRouter, HTTPException, status
from app.models import DimensionScoreUpdate, DimensionScoreResponse
from app.models.enums import Dimension
from app.pipelines.dimension_scorer import DimensionScoringPipeline
from app.services import get_snowflake_service, get_redis_cache, CacheKeys

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