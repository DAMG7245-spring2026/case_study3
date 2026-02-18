"""Document API endpoints for SEC filings."""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.models.document import (
    DocumentCollectionRequest,
    DocumentCollectAllRequest,
    DocumentCollectionResponse,
    DocumentResponse,
    DocumentChunkResponse,
    DocumentStatus,
)
from app.services.snowflake import SnowflakeService, get_snowflake_service
from app.services.s3_storage import S3Storage, get_s3_storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

# In-memory task logs for UI: task_id -> {"lines": list[str], "finished": bool}
_TASK_LOGS: dict[str, dict] = {}


# --- Response Models ---

class PaginatedDocuments(BaseModel):
    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PaginatedChunks(BaseModel):
    items: list[DocumentChunkResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# --- Endpoints ---

@router.post("/collect", response_model=DocumentCollectionResponse)
async def collect_documents(
    request: DocumentCollectionRequest,
    background_tasks: BackgroundTasks,
    db: SnowflakeService = Depends(get_snowflake_service),
    s3: S3Storage = Depends(get_s3_storage)
):
    """Trigger document collection for a company."""
    task_id = str(uuid4())
    _TASK_LOGS[task_id] = {"lines": [], "finished": False}

    background_tasks.add_task(
        _run_document_collection,
        task_id=task_id,
        company_id=request.company_id,
        filing_types=request.filing_types,
        years_back=request.years_back,
        db=db,
        s3=s3
    )
    
    return DocumentCollectionResponse(
        task_id=task_id,
        status="queued",
        message=f"Document collection started for company {request.company_id}"
    )


@router.post("/collect-all", response_model=DocumentCollectionResponse)
async def collect_documents_all(
    request: DocumentCollectAllRequest,
    background_tasks: BackgroundTasks,
    db: SnowflakeService = Depends(get_snowflake_service),
    s3: S3Storage = Depends(get_s3_storage)
):
    """Trigger document collection for all companies."""
    rows = db.execute_query(
        "SELECT id FROM companies WHERE is_deleted = FALSE ORDER BY ticker",
        ()
    )
    company_ids = [UUID(r["id"]) for r in rows] if rows else []
    if not company_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No companies found. Add companies first."
        )
    task_id = str(uuid4())
    _TASK_LOGS[task_id] = {"lines": [], "finished": False}
    background_tasks.add_task(
        _run_document_collection_all,
        task_id=task_id,
        company_ids=company_ids,
        filing_types=request.filing_types,
        years_back=request.years_back,
        db=db,
        s3=s3
    )
    return DocumentCollectionResponse(
        task_id=task_id,
        status="queued",
        message=f"Document collection started for {len(company_ids)} companies"
    )


@router.get("/collect/logs/{task_id}")
async def get_collect_logs(task_id: str):
    """Get log lines for a document collection task (for UI scrollable log view)."""
    if task_id not in _TASK_LOGS:
        return {"task_id": task_id, "logs": [], "finished": False}
    entry = _TASK_LOGS[task_id]
    return {"task_id": task_id, "logs": entry["lines"], "finished": entry["finished"]}


@router.get("", response_model=PaginatedDocuments)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    company_id: Optional[UUID] = None,
    ticker: Optional[str] = None,
    filing_type: Optional[str] = None,
    doc_status: Optional[DocumentStatus] = Query(None, alias="status"),
    db: SnowflakeService = Depends(get_snowflake_service)
):
    """List documents with optional filtering and pagination."""
    offset = (page - 1) * page_size
    
    docs = db.get_documents(
        company_id=company_id,
        ticker=ticker,
        filing_type=filing_type,
        status=doc_status.value if doc_status else None,
        limit=page_size,
        offset=offset
    )
    
    total = db.count_documents(
        company_id=company_id,
        ticker=ticker,
        filing_type=filing_type,
        status=doc_status.value if doc_status else None
    )
    
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    
    return PaginatedDocuments(
        items=[DocumentResponse(**d) for d in docs],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    db: SnowflakeService = Depends(get_snowflake_service)
):
    """Get a document by ID."""
    doc = db.get_document(str(document_id))
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found"
        )
    
    return DocumentResponse(**doc)


@router.get("/{document_id}/chunks", response_model=PaginatedChunks)
async def get_document_chunks(
    document_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    section: Optional[str] = None,
    db: SnowflakeService = Depends(get_snowflake_service)
):
    """Get chunks for a document."""
    doc = db.get_document(str(document_id))
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found"
        )
    
    offset = (page - 1) * page_size
    
    chunks = db.get_chunks(
        document_id=str(document_id),
        section=section,
        limit=page_size,
        offset=offset
    )
    
    total = db.count_chunks(str(document_id))
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    
    return PaginatedChunks(
        items=[DocumentChunkResponse(**c) for c in chunks],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/{document_id}/download-url")
async def get_document_download_url(
    document_id: UUID,
    expiration: int = Query(3600, ge=60, le=86400),
    db: SnowflakeService = Depends(get_snowflake_service),
    s3: S3Storage = Depends(get_s3_storage)
):
    """Get a presigned URL to download the original document from S3."""
    doc = db.get_document(str(document_id))
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found"
        )
    
    s3_key = doc.get("s3_key")
    if not s3_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not uploaded to S3"
        )
    
    url = s3.get_sec_filing_url(s3_key, expiration)
    if not url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate download URL"
        )
    
    return {"download_url": url, "expires_in": expiration}


# --- Background Tasks ---

def _run_document_collection_for_company(
    task_id: str,
    company_id: UUID,
    filing_types: list[str],
    years_back: int,
    db: SnowflakeService,
    s3: S3Storage,
    log: callable,
):
    """Run document collection for a single company. log(msg, level) is called for each log line."""
    from pathlib import Path
    from app.pipelines import SECEdgarPipeline, DocumentParser, SemanticChunker
    from app.config import get_settings

    settings = get_settings()
    company = db.execute_one(
        "SELECT id, ticker, name FROM companies WHERE id = %s AND is_deleted = FALSE",
        (str(company_id),)
    )
    if not company:
        log(f"Task {task_id}: Company {company_id} not found", "error")
        return
    ticker = company["ticker"]
    log(f"Task {task_id}: Collecting documents for {ticker}")

    email = getattr(settings, 'sec_edgar_email', 'student@university.edu')
    pipeline = SECEdgarPipeline(company_name="PE-OrgAIR-Platform", email=email)
    parser = DocumentParser()
    chunker = SemanticChunker()

    after_date = f"{datetime.now().year - years_back}-01-01"
    filings = pipeline.download_filings(
        ticker=ticker,
        filing_types=filing_types,
        limit=10,
        after=after_date
    )
    log(f"Task {task_id}: Downloaded {len(filings)} filings for {ticker}")

    docs_processed = 0
    for filing_path in filings:
        try:
            filing_path = Path(filing_path)
            parsed = parser.parse_filing(filing_path, ticker)
            existing = db.execute_one(
                "SELECT id FROM documents WHERE content_hash = %s",
                (parsed.content_hash,)
            )
            if existing:
                log(f"Task {task_id}: Skipping duplicate {parsed.filing_type}")
                continue
            filing_date_str = parsed.filing_date.strftime("%Y-%m-%d")
            s3_key = s3.upload_sec_filing(
                ticker=ticker,
                filing_type=parsed.filing_type,
                filing_date=filing_date_str,
                local_path=filing_path,
                content_hash=parsed.content_hash
            )
            if not s3_key:
                log(f"Task {task_id}: Failed to upload to S3, continuing without S3 key", "warning")
            accession_dir = filing_path.parent
            for sibling in accession_dir.glob("primary-document.*"):
                s3.upload_sec_filing_as_pdf(
                    ticker=ticker,
                    filing_type=parsed.filing_type,
                    filing_date=filing_date_str,
                    local_path=sibling,
                    content_hash=parsed.content_hash
                )
            doc_id = db.insert_document(
                company_id=company_id,
                ticker=ticker,
                filing_type=parsed.filing_type,
                filing_date=parsed.filing_date,
                content_hash=parsed.content_hash,
                word_count=parsed.word_count,
                local_path=str(filing_path),
                s3_key=s3_key,
                status="parsed"
            )
            parsed.document_id = doc_id
            chunks = chunker.chunk_document(parsed)
            chunk_dicts = [
                {"chunk_index": c.chunk_index, "content": c.content, "section": c.section,
                 "start_char": c.start_char, "end_char": c.end_char, "word_count": c.word_count}
                for c in chunks
            ]
            db.insert_chunks(doc_id, chunk_dicts)
            db.update_document_status(doc_id, "chunked", chunk_count=len(chunks))
            docs_processed += 1
            log(f"Task {task_id}: Processed {parsed.filing_type} ({len(chunks)} chunks, S3: {s3_key is not None})")
        except Exception as e:
            log(f"Task {task_id}: Error processing {filing_path}: {e}", "error")
            try:
                doc_id = db.insert_document(
                    company_id=company_id,
                    ticker=ticker,
                    filing_type="unknown",
                    filing_date=datetime.now(timezone.utc),
                    local_path=str(filing_path),
                    status="failed"
                )
                db.update_document_status(doc_id, "failed", error_message=str(e))
            except Exception:
                pass
    log(f"Task {task_id}: {ticker} done: {docs_processed}/{len(filings)} documents processed")


def _run_document_collection(
    task_id: str,
    company_id: UUID,
    filing_types: list[str],
    years_back: int,
    db: SnowflakeService,
    s3: S3Storage
):
    """Background task for document collection with S3 upload. Appends logs to _TASK_LOGS for UI."""
    def log(msg: str, level: str = "info"):
        logger.info(msg) if level == "info" else logger.warning(msg) if level == "warning" else logger.error(msg)
        if task_id in _TASK_LOGS:
            _TASK_LOGS[task_id]["lines"].append(msg)

    log(f"Starting document collection task {task_id} for company {company_id}")
    try:
        _run_document_collection_for_company(
            task_id, company_id, filing_types, years_back, db, s3, log
        )
    except Exception as e:
        log(f"Task {task_id} failed: {e}", "error")
    finally:
        _TASK_LOGS[task_id]["finished"] = True


def _run_document_collection_all(
    task_id: str,
    company_ids: list,
    filing_types: list[str],
    years_back: int,
    db: SnowflakeService,
    s3: S3Storage
):
    """Background task: run document collection for each company. Single task_id, aggregated logs."""
    def log(msg: str, level: str = "info"):
        logger.info(msg) if level == "info" else logger.warning(msg) if level == "warning" else logger.error(msg)
        if task_id in _TASK_LOGS:
            _TASK_LOGS[task_id]["lines"].append(msg)

    log(f"Starting document collection for all companies (task {task_id}, {len(company_ids)} companies)")
    try:
        for i, company_id in enumerate(company_ids):
            log(f"--- Company {i + 1}/{len(company_ids)} ---")
            try:
                _run_document_collection_for_company(
                    task_id, company_id, filing_types, years_back, db, s3, log
                )
            except Exception as e:
                log(f"Task {task_id}: Company {company_id} failed: {e}", "error")
    finally:
        _TASK_LOGS[task_id]["finished"] = True
        log(f"Task {task_id} completed: finished all {len(company_ids)} companies")
