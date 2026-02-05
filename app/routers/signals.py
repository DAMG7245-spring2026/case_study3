"""Signal API endpoints for external data sources."""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.models.signal import (
    SignalCategory,
    SignalCollectionRequest,
    SignalCollectionResponse,
    ExternalSignalResponse,
    CompanySignalSummaryResponse,
)
from app.services.snowflake import SnowflakeService, get_snowflake_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["signals"])


# --- Response Models ---

class PaginatedSignals(BaseModel):
    items: list[ExternalSignalResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# --- Signal Collection Endpoints ---

@router.post("/signals/collect", response_model=SignalCollectionResponse)
async def collect_signals(
    request: SignalCollectionRequest,
    background_tasks: BackgroundTasks,
    db: SnowflakeService = Depends(get_snowflake_service)
):
    """Trigger signal collection for a company."""
    task_id = str(uuid4())
    
    background_tasks.add_task(
        _run_signal_collection,
        task_id=task_id,
        company_id=request.company_id,
        categories=request.categories,
        db=db
    )
    
    return SignalCollectionResponse(
        task_id=task_id,
        status="queued",
        message=f"Signal collection started for company {request.company_id}"
    )


@router.get("/signals", response_model=PaginatedSignals)
async def list_signals(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    company_id: Optional[UUID] = None,
    category: Optional[SignalCategory] = None,
    db: SnowflakeService = Depends(get_snowflake_service)
):
    """List signals with optional filtering."""
    offset = (page - 1) * page_size
    
    signals = db.get_signals(
        company_id=company_id,
        category=category.value if category else None,
        limit=page_size,
        offset=offset
    )
    
    total = db.count_signals(
        company_id=company_id,
        category=category.value if category else None
    )
    
    total_pages = (total + page_size - 1) // page_size
    
    return PaginatedSignals(
        items=[ExternalSignalResponse(**s) for s in signals],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


# --- Company Signal Endpoints ---

@router.get("/companies/{company_id}/signals", response_model=CompanySignalSummaryResponse)
async def get_company_signal_summary(
    company_id: UUID,
    db: SnowflakeService = Depends(get_snowflake_service)
):
    """Get signal summary for a company."""
    summary = db.get_signal_summary(company_id)
    
    if not summary:
        # Return empty summary
        return CompanySignalSummaryResponse(
            company_id=company_id,
            ticker="UNKNOWN",
            technology_hiring_score=0,
            innovation_activity_score=0,
            digital_presence_score=0,
            leadership_signals_score=0,
            signal_count=0,
            last_updated=datetime.now(timezone.utc)
        )
    
    return CompanySignalSummaryResponse(**summary)


@router.get("/companies/{company_id}/signals/{category}", response_model=list[ExternalSignalResponse])
async def get_company_signals_by_category(
    company_id: UUID,
    category: SignalCategory,
    db: SnowflakeService = Depends(get_snowflake_service)
):
    """Get signals for a company by category."""
    signals = db.get_signals(
        company_id=company_id,
        category=category.value
    )
    
    return [ExternalSignalResponse(**s) for s in signals]


# --- Background Tasks ---

def _run_signal_collection(
    task_id: str,
    company_id: UUID,
    categories: list[SignalCategory],
    db: SnowflakeService
):
    """Background task for signal collection."""
    logger.info(f"Starting signal collection task {task_id} for company {company_id}")
    
    try:
        from app.pipelines import JobSignalCollector, TechStackCollector, PatentSignalCollector
        
        # Get company info
        # For demo, we'll use sample data
        company_name = "Company"  # Would come from DB lookup
        ticker = "UNKNOWN"
        
        signals_collected = []
        
        if SignalCategory.TECHNOLOGY_HIRING in categories:
            collector = JobSignalCollector()
            postings = collector.create_sample_postings(company_name, ai_focus="medium")
            signal = collector.analyze_job_postings(company_name, postings, company_id)
            
            db.insert_signal(
                company_id=company_id,
                category=signal.category.value,
                source=signal.source.value,
                signal_date=signal.signal_date,
                raw_value=signal.raw_value,
                normalized_score=signal.normalized_score,
                confidence=signal.confidence,
                metadata=signal.metadata
            )
            signals_collected.append(signal)
        
        if SignalCategory.DIGITAL_PRESENCE in categories:
            collector = TechStackCollector()
            techs = collector.create_sample_technologies(ai_maturity="medium")
            signal = collector.analyze_tech_stack(company_id, techs)
            
            db.insert_signal(
                company_id=company_id,
                category=signal.category.value,
                source=signal.source.value,
                signal_date=signal.signal_date,
                raw_value=signal.raw_value,
                normalized_score=signal.normalized_score,
                confidence=signal.confidence,
                metadata=signal.metadata
            )
            signals_collected.append(signal)
        
        if SignalCategory.INNOVATION_ACTIVITY in categories:
            collector = PatentSignalCollector()
            patents = collector.create_sample_patents(company_name, ai_innovation="medium")
            signal = collector.analyze_patents(company_id, patents)
            
            db.insert_signal(
                company_id=company_id,
                category=signal.category.value,
                source=signal.source.value,
                signal_date=signal.signal_date,
                raw_value=signal.raw_value,
                normalized_score=signal.normalized_score,
                confidence=signal.confidence,
                metadata=signal.metadata
            )
            signals_collected.append(signal)
        
        # Update summary
        if signals_collected:
            hiring_score = next((s.normalized_score for s in signals_collected if s.category == SignalCategory.TECHNOLOGY_HIRING), 0)
            innovation_score = next((s.normalized_score for s in signals_collected if s.category == SignalCategory.INNOVATION_ACTIVITY), 0)
            digital_score = next((s.normalized_score for s in signals_collected if s.category == SignalCategory.DIGITAL_PRESENCE), 0)
            
            db.upsert_signal_summary(
                company_id=company_id,
                ticker=ticker,
                technology_hiring_score=hiring_score,
                innovation_activity_score=innovation_score,
                digital_presence_score=digital_score,
                leadership_signals_score=50.0,  # Placeholder
                signal_count=len(signals_collected)
            )
        
        logger.info(f"Task {task_id} completed: {len(signals_collected)} signals collected")
        
    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}")