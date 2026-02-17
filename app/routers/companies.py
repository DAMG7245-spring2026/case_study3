"""Company CRUD endpoints."""
import math
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4
from fastapi import APIRouter, HTTPException, Query, status
from app.config import get_settings
from app.models import (
    CompanyCreate, CompanyUpdate, CompanyResponse,
    PaginatedResponse, MessageResponse, IndustryResponse
)
from app.services import get_snowflake_service, get_redis_cache, CacheKeys

router = APIRouter(prefix="/api/v1/companies", tags=["Companies"])

_COMPANY_COLS = "id, name, ticker, industry_id, position_factor, domain, careers_url, news_url, leadership_url, created_at, updated_at"


def _row_to_company_response(row: dict) -> CompanyResponse:
    """Build CompanyResponse from DB row (with URL columns)."""
    return CompanyResponse(
        id=UUID(row["id"]),
        name=row["name"],
        ticker=row["ticker"],
        industry_id=UUID(row["industry_id"]),
        position_factor=float(row["position_factor"] or 0),
        domain=row.get("domain"),
        careers_url=row.get("careers_url"),
        news_url=row.get("news_url"),
        leadership_url=row.get("leadership_url"),
        created_at=row["created_at"],
        updated_at=row["updated_at"]
    )


@router.post(
    "",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Company"
)
async def create_company(company: CompanyCreate):
    """Create a new company."""
    db = get_snowflake_service()
    ticker_norm = (company.ticker or "").strip().upper()
    if not ticker_norm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ticker is required"
        )

    # Reject duplicate ticker
    existing = db.execute_one(
        "SELECT id FROM companies WHERE ticker = %s AND is_deleted = FALSE",
        (ticker_norm,)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A company with this ticker already exists."
        )

    # Verify industry exists
    industry = db.execute_one(
        "SELECT id FROM industries WHERE id = %s",
        (str(company.industry_id),)
    )
    if not industry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Industry {company.industry_id} not found"
        )

    company_id = str(uuid4())
    now = datetime.now(timezone.utc)

    db.execute_write(
        """
        INSERT INTO companies (id, name, ticker, industry_id, position_factor,
            domain, careers_url, news_url, leadership_url, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            company_id, company.name, ticker_norm, str(company.industry_id),
            company.position_factor,
            company.domain or None, company.careers_url or None,
            company.news_url or None, company.leadership_url or None,
            now, now
        )
    )

    row = db.execute_one(
        "SELECT id, name, ticker, industry_id, position_factor, domain, careers_url, news_url, leadership_url, created_at, updated_at FROM companies WHERE id = %s",
        (company_id,)
    )
    return _row_to_company_response(row)


@router.get(
    "",
    response_model=PaginatedResponse[CompanyResponse],
    summary="List Companies"
)
async def list_companies(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    industry_id: Optional[UUID] = Query(None, description="Filter by industry")
):
    """List companies with pagination and optional filtering."""
    db = get_snowflake_service()
    
    # Build query
    base_query = "FROM companies WHERE is_deleted = FALSE"
    params = []
    
    if industry_id:
        base_query += " AND industry_id = %s"
        params.append(str(industry_id))
    
    # Get total count
    count_result = db.execute_one(f"SELECT COUNT(*) as count {base_query}", tuple(params))
    total = count_result["count"] if count_result else 0
    
    # Get paginated results
    offset = (page - 1) * page_size
    query = f"""
        SELECT {_COMPANY_COLS}
        {base_query}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """
    params.extend([page_size, offset])
    rows = db.execute_query(query, tuple(params))
    items = [_row_to_company_response(row) for row in rows]
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0
    )


@router.get(
    "/{company_id}",
    response_model=CompanyResponse,
    summary="Get Company"
)
async def get_company(company_id: UUID):
    """Get a company by ID."""
    cache = get_redis_cache()
    settings = get_settings()
    cache_key = CacheKeys.company(str(company_id))
    
    # Try cache first
    cached = cache.get(cache_key, CompanyResponse)
    if cached:
        return cached
    
    # Fetch from database
    db = get_snowflake_service()
    row = db.execute_one(
        f"SELECT {_COMPANY_COLS} FROM companies WHERE id = %s AND is_deleted = FALSE",
        (str(company_id),)
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found"
        )
    company = _row_to_company_response(row)
    
    # Cache for 5 minutes
    cache.set(cache_key, company, settings.cache_ttl_company)
    
    return company


@router.put(
    "/{company_id}",
    response_model=CompanyResponse,
    summary="Update Company"
)
async def update_company(company_id: UUID, update: CompanyUpdate):
    """Update a company."""
    db = get_snowflake_service()
    cache = get_redis_cache()
    
    # Check company exists
    existing = db.execute_one(
        "SELECT id FROM companies WHERE id = %s AND is_deleted = FALSE",
        (str(company_id),)
    )
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found"
        )
    
    # Build update query dynamically (only allowed columns)
    allowed = {"name", "ticker", "industry_id", "position_factor", "domain", "careers_url", "news_url", "leadership_url"}
    updates = []
    params = []
    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field not in allowed:
            continue
        if field == "industry_id" and value is not None:
            value = str(value)
        updates.append(f"{field} = %s")
        params.append(value)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    updates.append("updated_at = %s")
    params.append(datetime.now(timezone.utc))
    params.append(str(company_id))
    
    db.execute_write(
        f"UPDATE companies SET {', '.join(updates)} WHERE id = %s",
        tuple(params)
    )
    
    # Invalidate cache
    cache.delete(CacheKeys.company(str(company_id)))
    
    # Return updated company
    return await get_company(company_id)


@router.delete(
    "/{company_id}",
    response_model=MessageResponse,
    summary="Delete Company"
)
async def delete_company(company_id: UUID):
    """Soft delete a company."""
    db = get_snowflake_service()
    cache = get_redis_cache()
    
    # Check company exists
    existing = db.execute_one(
        "SELECT id FROM companies WHERE id = %s AND is_deleted = FALSE",
        (str(company_id),)
    )
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found"
        )
    
    # Soft delete
    db.execute_write(
        "UPDATE companies SET is_deleted = TRUE, updated_at = %s WHERE id = %s",
        (datetime.now(timezone.utc), str(company_id))
    )
    
    # Invalidate cache
    cache.delete(CacheKeys.company(str(company_id)))
    
    return MessageResponse(
        message=f"Company {company_id} deleted successfully",
        id=str(company_id)
    )