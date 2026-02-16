"""Document models for SEC filings and parsed content."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DocumentStatus(str, Enum):
    """Status of document processing pipeline."""
    PENDING = "pending"
    DOWNLOADED = "downloaded"
    PARSED = "parsed"
    CHUNKED = "chunked"
    INDEXED = "indexed"
    FAILED = "failed"


class FilingType(str, Enum):
    """SEC filing types."""
    FORM_10K = "10-K"
    FORM_10Q = "10-Q"
    FORM_8K = "8-K"
    DEF_14A = "DEF-14A"


# --- Base Models ---

class DocumentBase(BaseModel):
    """Base document model."""
    company_id: UUID
    ticker: str = Field(..., max_length=10)
    filing_type: str = Field(..., max_length=20)
    filing_date: datetime


class DocumentChunkBase(BaseModel):
    """Base chunk model."""
    document_id: UUID
    chunk_index: int = Field(..., ge=0)
    content: str
    section: Optional[str] = Field(None, max_length=50)
    start_char: Optional[int] = Field(None, ge=0)
    end_char: Optional[int] = Field(None, ge=0)
    word_count: Optional[int] = Field(None, ge=0)


# --- Create Models ---

class DocumentCreate(DocumentBase):
    """Model for creating a document record."""
    source_url: Optional[str] = Field(None, max_length=500)
    local_path: Optional[str] = Field(None, max_length=500)
    s3_key: Optional[str] = Field(None, max_length=500)
    content_hash: Optional[str] = Field(None, max_length=64)
    word_count: Optional[int] = Field(None, ge=0)


class DocumentChunkCreate(DocumentChunkBase):
    """Model for creating a document chunk."""
    pass


# --- Response Models ---

class DocumentResponse(DocumentBase):
    """Response model for document."""
    id: UUID
    source_url: Optional[str] = None
    local_path: Optional[str] = None
    s3_key: Optional[str] = None
    content_hash: Optional[str] = None
    word_count: Optional[int] = None
    chunk_count: Optional[int] = None
    status: DocumentStatus = DocumentStatus.PENDING
    error_message: Optional[str] = None
    created_at: datetime
    processed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentChunkResponse(DocumentChunkBase):
    """Response model for document chunk."""
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


# --- Internal Processing Models ---

class ParsedDocument(BaseModel):
    """Represents a fully parsed SEC document."""
    document_id: Optional[str] = None  # UUID from documents table, set after DB insert
    company_ticker: str
    filing_type: str
    filing_date: datetime
    content: str
    sections: dict[str, str] = Field(default_factory=dict)
    source_path: str
    content_hash: str
    word_count: int


class DocumentChunk(BaseModel):
    """A chunk of a document for processing."""
    document_id: str
    chunk_index: int
    content: str
    section: Optional[str] = None
    start_char: int
    end_char: int
    word_count: int


# --- Request Models ---

class DocumentCollectionRequest(BaseModel):
    """Request to trigger document collection."""
    company_id: UUID
    filing_types: list[str] = Field(default=["10-K", "10-Q", "8-K"])
    years_back: int = Field(default=3, ge=1, le=10)


class DocumentCollectionResponse(BaseModel):
    """Response from document collection trigger."""
    task_id: str
    status: str
    message: str