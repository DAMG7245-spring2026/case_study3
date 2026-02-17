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
    SignalSource,
)
from app.services.snowflake import SnowflakeService, get_snowflake_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["signals"])

# In-memory task logs for UI: task_id -> {"lines": list[str], "finished": bool}
_SIGNAL_TASK_LOGS: dict[str, dict] = {}


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
    _SIGNAL_TASK_LOGS[task_id] = {"lines": [], "finished": False}

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


@router.get("/signals/collect/logs/{task_id}")
async def get_signal_collect_logs(task_id: str):
    """Get log lines for a signal collection task (for UI scrollable log view)."""
    if task_id not in _SIGNAL_TASK_LOGS:
        return {"task_id": task_id, "logs": [], "finished": False}
    entry = _SIGNAL_TASK_LOGS[task_id]
    return {"task_id": task_id, "logs": entry["lines"], "finished": entry["finished"]}


# --- Formulas (for UI display) ---

SIGNAL_FORMULAS = {
    "technology_hiring": (
        "Score = min(ai_ratio * 60, 60) + min(skill_diversity / 10, 1) * 20 + min(ai_jobs / 5, 1) * 20. "
        "raw_value = '{ai_jobs}/{total_tech_jobs} AI jobs'. "
        "ai_ratio = AI-related jobs / total tech jobs; skill_diversity = count of distinct AI skills found."
    ),
    "innovation_activity": "Score from AI-related patents count and recency. raw_value = '{n} AI patents in {years} years'.",
    "digital_presence": "Score from tech stack (BuiltWith) and news page. raw_value combines AI tech count and article metrics.",
    "leadership_signals": "Score from leadership/commitment keywords on company or leadership URL. raw_value = summary of keyword hits.",
}


@router.get("/signals/formulas")
async def get_signal_formulas():
    """Return formula descriptions per category for UI display."""
    return {"formulas": SIGNAL_FORMULAS}


# --- Compute (from stored raw data) ---

class SignalComputeRequest(BaseModel):
    company_id: UUID
    categories: list[str] = []  # empty = all categories that have raw data


class SignalComputeResponse(BaseModel):
    computed: list[str]
    message: str


@router.post("/signals/compute", response_model=SignalComputeResponse)
async def compute_signals(
    request: SignalComputeRequest,
    db: SnowflakeService = Depends(get_snowflake_service),
):
    """Compute signal scores from stored raw data and write to external_signals and company_signal_summaries."""
    company_id = request.company_id
    categories = request.categories
    computed: list[str] = []

    company = db.get_company_by_id(company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    name = company.get("name") or "Unknown"
    ticker = (company.get("ticker") or "UNKNOWN").upper()

    if not categories:
        categories = ["technology_hiring", "innovation_activity", "digital_presence", "leadership_signals"]

    hiring_score = 0.0
    innovation_score = 0.0
    digital_score = 0.0
    leadership_score = 0.0
    signals_added = 0

    existing_summary = db.get_signal_summary(company_id)
    if existing_summary:
        hiring_score = float(existing_summary.get("technology_hiring_score") or 0)
        innovation_score = float(existing_summary.get("innovation_activity_score") or 0)
        digital_score = float(existing_summary.get("digital_presence_score") or 0)
        leadership_score = float(existing_summary.get("leadership_signals_score") or 0)

    if "technology_hiring" in categories:
        raw_row = db.get_raw_collection(company_id, "technology_hiring")
        if raw_row and raw_row.get("payload"):
            from app.pipelines.job_signals import JobSignalCollector
            from app.models.signal import JobPosting

            payload = raw_row["payload"]
            if isinstance(payload, list) and len(payload) > 0:
                db.delete_signals_by_company_and_category(company_id, "technology_hiring")
                postings = [JobPosting(**item) for item in payload]
                collector = JobSignalCollector()
                signal = collector.analyze_job_postings(name, postings, company_id)
                source = getattr(signal.source, "value", str(signal.source)) if hasattr(signal, "source") else "careers_and_serp"
                db.insert_signal(
                    company_id=company_id,
                    category=signal.category.value,
                    source=source,
                    signal_date=signal.signal_date,
                    raw_value=signal.raw_value,
                    normalized_score=signal.normalized_score,
                    confidence=signal.confidence,
                    metadata=signal.metadata,
                )
                hiring_score = signal.normalized_score
                signals_added += 1
                computed.append("technology_hiring")

    if "innovation_activity" in categories:
        raw_row = db.get_raw_collection(company_id, "innovation_activity")
        if raw_row and raw_row.get("payload"):
            from app.pipelines.patent_signals import PatentSignalCollector
            from app.models.signal import Patent

            payload = raw_row["payload"]
            if isinstance(payload, list) and len(payload) > 0:
                db.delete_signals_by_company_and_category(company_id, "innovation_activity")
                patents = [Patent.model_validate(p) for p in payload]
                patent_collector = PatentSignalCollector()
                signal = patent_collector.analyze_patents(company_id, patents)
                db.insert_signal(
                    company_id=company_id,
                    category=signal.category.value,
                    source=signal.source.value,
                    signal_date=signal.signal_date,
                    raw_value=signal.raw_value,
                    normalized_score=signal.normalized_score,
                    confidence=signal.confidence,
                    metadata=signal.metadata,
                )
                innovation_score = signal.normalized_score
                signals_added += 1
                computed.append("innovation_activity")

    if "digital_presence" in categories:
        raw_row = db.get_raw_collection(company_id, "digital_presence")
        if raw_row and raw_row.get("payload"):
            from app.pipelines.digital_presence_signals import DigitalPresenceCollector
            from app.models.signal import TechnologyDetection

            payload = raw_row["payload"]
            if isinstance(payload, dict):
                db.delete_signals_by_company_and_category(company_id, "digital_presence")
                tech_list = payload.get("tech_list") or []
                news_html = payload.get("news_html") or ""
                ticker_raw = payload.get("ticker") or ticker
                dp = DigitalPresenceCollector()
                if tech_list:
                    techs = [TechnologyDetection(**t) for t in tech_list]
                    tech_signal = dp.tech_collector.analyze_tech_stack(company_id, techs)
                    db.insert_signal(
                        company_id=company_id,
                        category=tech_signal.category.value,
                        source=tech_signal.source.value,
                        signal_date=tech_signal.signal_date,
                        raw_value=tech_signal.raw_value,
                        normalized_score=tech_signal.normalized_score,
                        confidence=tech_signal.confidence,
                        metadata=tech_signal.metadata,
                    )
                    digital_score = max(digital_score, tech_signal.normalized_score)
                    signals_added += 1
                news_signal = dp.news_collector.analyze_news(company_id, ticker_raw, news_html)
                if news_signal and news_signal.normalized_score > 0:
                    db.insert_signal(
                        company_id=company_id,
                        category=news_signal.category.value,
                        source=news_signal.source.value,
                        signal_date=news_signal.signal_date,
                        raw_value=news_signal.raw_value,
                        normalized_score=news_signal.normalized_score,
                        confidence=news_signal.confidence,
                        metadata=news_signal.metadata,
                    )
                    digital_score = max(digital_score, news_signal.normalized_score)
                    signals_added += 1
                if tech_list or (news_signal and news_signal.normalized_score > 0):
                    computed.append("digital_presence")

    if "leadership_signals" in categories:
        raw_row = db.get_raw_collection(company_id, "leadership_signals")
        if raw_row and raw_row.get("payload"):
            from app.pipelines.leadership_signals import LeadershipSignalCollector

            payload = raw_row["payload"]
            if isinstance(payload, dict) and payload.get("text"):
                db.delete_signals_by_company_and_category(company_id, "leadership_signals")
                leadership_collector = LeadershipSignalCollector()
                leadership_signals = leadership_collector.analyze_leadership(
                    company_id, website_data=payload
                )
                for sig in leadership_signals:
                    db.insert_signal(
                        company_id=company_id,
                        category=sig.category.value,
                        source=sig.source.value,
                        signal_date=sig.signal_date,
                        raw_value=sig.raw_value,
                        normalized_score=sig.normalized_score,
                        confidence=sig.confidence,
                        metadata=sig.metadata,
                    )
                    leadership_score = max(leadership_score, sig.normalized_score)
                    signals_added += 1
                if leadership_signals:
                    computed.append("leadership_signals")

    signal_count = db.count_signals(company_id=company_id)
    db.upsert_signal_summary(
        company_id=company_id,
        ticker=ticker,
        technology_hiring_score=hiring_score,
        innovation_activity_score=innovation_score,
        digital_presence_score=digital_score,
        leadership_signals_score=leadership_score,
        signal_count=signal_count,
    )

    return SignalComputeResponse(
        computed=computed,
        message=f"Computed {len(computed)} categories." if computed else "No raw data found for selected categories.",
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
    """Background task for signal collection. Appends logs to _SIGNAL_TASK_LOGS for UI."""
    def log(msg: str, level: str = "info"):
        logger.info(msg) if level == "info" else logger.error(msg)
        if task_id in _SIGNAL_TASK_LOGS:
            _SIGNAL_TASK_LOGS[task_id]["lines"].append(msg)

    log(f"Starting signal collection task {task_id} for company {company_id}")

    try:
        from app.pipelines import (
            JobSignalCollector,
            DigitalPresenceCollector,
            PatentSignalCollector,
            LeadershipSignalCollector,
        )
        from app.config import get_settings

        company = db.get_company_by_id(company_id)
        if not company:
            log(f"Task {task_id}: Company {company_id} not found", "error")
            _SIGNAL_TASK_LOGS[task_id]["finished"] = True
            return

        ticker = (company.get("ticker") or "UNKNOWN").upper()
        name = company.get("name") or "Unknown"
        domain = company.get("domain") or ""
        settings = get_settings()

        job_collector = JobSignalCollector()
        digital_presence_collector = DigitalPresenceCollector()
        patent_collector = PatentSignalCollector()

        existing_summary = db.get_signal_summary(company_id)
        hiring_score = float(existing_summary.get("technology_hiring_score") or 0) if existing_summary else 0.0
        digital_score = float(existing_summary.get("digital_presence_score") or 0) if existing_summary else 0.0
        innovation_score = float(existing_summary.get("innovation_activity_score") or 0) if existing_summary else 0.0
        leadership_score = float(existing_summary.get("leadership_signals_score") or 0) if existing_summary else 0.0

        if SignalCategory.TECHNOLOGY_HIRING in categories:
            careers_url = company.get("careers_url") if isinstance(company.get("careers_url"), str) else None
            postings = []
            if careers_url:
                postings.extend(job_collector.fetch_postings_from_careers_page(careers_url, name))
            serp_postings = job_collector.fetch_postings(name, api_key=settings.serpapi_key or None)
            if serp_postings:
                postings.extend(serp_postings)
            jobspy_postings = job_collector.fetch_postings_from_jobspy(name, location="United States", results_wanted=20)
            if jobspy_postings:
                postings.extend(jobspy_postings)
            postings = job_collector._dedupe_postings_by_title(postings) if postings else []
            if postings:
                for p in postings:
                    job_collector.classify_posting(p)
                payload = [p.model_dump() for p in postings]
                db.insert_or_replace_raw_collection(company_id, "technology_hiring", payload)
                log(f"Task {task_id}: Stored {len(postings)} job postings (raw). Use Compute to get score.")
                if existing_summary and existing_summary.get("technology_hiring_score") is not None:
                    hiring_score = float(existing_summary["technology_hiring_score"])

        if SignalCategory.DIGITAL_PRESENCE in categories:
            news_url = company.get("news_url") if isinstance(company.get("news_url"), str) else None
            techs = []
            if domain and getattr(settings, "builtwith_api_key", None):
                techs = digital_presence_collector.tech_collector.fetch_tech_stack(
                    domain, api_key=settings.builtwith_api_key
                )
            news_html = ""
            if news_url and news_url.strip():
                news_html = digital_presence_collector.news_collector.fetch_news_page(news_url) or ""
            payload = {
                "tech_list": [t.model_dump() for t in techs],
                "news_html": news_html,
                "ticker": ticker,
            }
            db.insert_or_replace_raw_collection(company_id, "digital_presence", payload)
            log(f"Task {task_id}: Stored digital_presence raw (techs={len(techs)}, news_len={len(news_html)}). Use Compute to get score.")
            if existing_summary and existing_summary.get("digital_presence_score") is not None:
                digital_score = float(existing_summary["digital_presence_score"])

        if SignalCategory.INNOVATION_ACTIVITY in categories:
            patents = patent_collector.fetch_patents(name, api_key=settings.lens_api_key or None)
            if patents:
                payload = [p.model_dump(mode="json") for p in patents]
                db.insert_or_replace_raw_collection(company_id, "innovation_activity", payload)
                log(f"Task {task_id}: Stored {len(patents)} patents (raw). Use Compute to get score.")
                if existing_summary and existing_summary.get("innovation_activity_score") is not None:
                    innovation_score = float(existing_summary["innovation_activity_score"])

        if SignalCategory.LEADERSHIP_SIGNALS in categories:
            leadership_collector = LeadershipSignalCollector()
            leadership_url = company.get("leadership_url") if isinstance(company.get("leadership_url"), str) else None
            if leadership_url:
                website_data = leadership_collector.fetch_leadership_page(leadership_url)
            else:
                website_data = None
            if not website_data:
                website_data = leadership_collector.fetch_from_company_website(domain)
            if website_data:
                payload = {"text": website_data.get("text", ""), "url": website_data.get("url", "")}
                db.insert_or_replace_raw_collection(company_id, "leadership_signals", payload)
                log(f"Task {task_id}: Stored leadership raw. Use Compute to get score.")
                if existing_summary and existing_summary.get("leadership_signals_score") is not None:
                    leadership_score = float(existing_summary["leadership_signals_score"])

        if SignalCategory.GLASSDOOR_REVIEWS in categories:
            from app.pipelines.glassdoor_collector import fetch_reviews as fetch_glassdoor_reviews

            reviews = fetch_glassdoor_reviews(company_name=name, ticker=ticker, limit=100)
            if reviews:
                payload = [r.model_dump(mode="json") for r in reviews]
                db.insert_or_replace_raw_collection(company_id, "glassdoor_reviews", payload)
                log(f"Task {task_id}: Stored {len(reviews)} Glassdoor reviews (raw).")
            else:
                log(f"Task {task_id}: No Glassdoor reviews found for ticker {ticker}.")

        signal_count = db.count_signals(company_id=company_id)
        db.upsert_signal_summary(
            company_id=company_id,
            ticker=ticker,
            technology_hiring_score=hiring_score,
            innovation_activity_score=innovation_score,
            digital_presence_score=digital_score,
            leadership_signals_score=leadership_score,
            signal_count=signal_count,
        )
        log(f"Task {task_id} completed: raw data stored for selected categories. Use Compute to populate signals.")
    except Exception as e:
        log(f"Task {task_id} failed: {e}", "error")
    finally:
        _SIGNAL_TASK_LOGS[task_id]["finished"] = True
