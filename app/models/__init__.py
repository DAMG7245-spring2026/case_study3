"""Pydantic models for PE Org-AI-R Platform."""

# Common Models
from app.models.common import (
    HealthResponse,
    PaginatedResponse,
    ErrorResponse,
    MessageResponse,
)

# Enums
from app.models.enums import (
    AssessmentType,
    AssessmentStatus,
    Dimension,
    DIMENSION_WEIGHTS,
    VALID_STATUS_TRANSITIONS,
)

# CS1 Models - Company
from app.models.company import (
    IndustryBase,
    IndustryCreate,
    IndustryResponse,
    CompanyBase,
    CompanyCreate,
    CompanyUpdate,
    CompanyResponse,
    CompanyWithIndustry,
)

# CS1 Models - Assessment
from app.models.assessment import (
    AssessmentBase,
    AssessmentCreate,
    AssessmentUpdate,
    AssessmentStatusUpdate,
    AssessmentResponse,
    AssessmentWithScores,
)

# CS1 Models - Dimension
from app.models.dimension import (
    DimensionScoreBase,
    DimensionScoreCreate,
    DimensionScoreBulkCreate,
    DimensionScoreUpdate,
    DimensionScoreResponse,
    DimensionScoreSummary,
)

# CS2 Models - Document
from app.models.document import (
    DocumentStatus,
    FilingType,
    DocumentBase,
    DocumentCreate,
    DocumentResponse,
    DocumentChunkBase,
    DocumentChunkCreate,
    DocumentChunkResponse,
    ParsedDocument,
    DocumentChunk,
    DocumentCollectionRequest,
    DocumentCollectionResponse,
)

# CS2 Models - Signal
from app.models.signal import (
    SignalCategory,
    SignalSource,
    ExternalSignalBase,
    ExternalSignalCreate,
    ExternalSignalResponse,
    CompanySignalSummaryBase,
    CompanySignalSummaryCreate,
    CompanySignalSummaryResponse,
    SignalCollectionRequest,
    SignalCollectionResponse,
    JobPosting,
    TechnologyDetection,
    Patent,
)

# CS2 Models - Evidence
from app.models.evidence import (
    CompanyEvidence,
    EvidenceStats,
    BackfillRequest,
    BackfillResponse,
)

# CS3 Models - Evidence Mapper
from app.pipelines.evidence_mapper.evidence_mapping_table import (
    DimensionMapping,
    EvidenceScore,
    DimensionScore,
    SIGNAL_TO_DIMENSION_MAP,
)

__all__ = [
    # Common
    "HealthResponse",
    "PaginatedResponse",
    "ErrorResponse",
    "MessageResponse",
    # Enums
    "AssessmentType",
    "AssessmentStatus",
    "Dimension",
    "DIMENSION_WEIGHTS",
    "VALID_STATUS_TRANSITIONS",
    # CS1 - Company
    "IndustryBase",
    "IndustryCreate",
    "IndustryResponse",
    "CompanyBase",
    "CompanyCreate",
    "CompanyUpdate",
    "CompanyResponse",
    "CompanyWithIndustry",
    # CS1 - Assessment
    "AssessmentBase",
    "AssessmentCreate",
    "AssessmentUpdate",
    "AssessmentStatusUpdate",
    "AssessmentResponse",
    "AssessmentWithScores",
    # CS1 - Dimension
    "DimensionScoreBase",
    "DimensionScoreCreate",
    "DimensionScoreBulkCreate",
    "DimensionScoreUpdate",
    "DimensionScoreResponse",
    "DimensionScoreSummary",
    # CS2 - Documents
    "DocumentStatus",
    "FilingType",
    "DocumentBase",
    "DocumentCreate",
    "DocumentResponse",
    "DocumentChunkBase",
    "DocumentChunkCreate",
    "DocumentChunkResponse",
    "ParsedDocument",
    "DocumentChunk",
    "DocumentCollectionRequest",
    "DocumentCollectionResponse",
    # CS2 - Signals
    "SignalCategory",
    "SignalSource",
    "ExternalSignalBase",
    "ExternalSignalCreate",
    "ExternalSignalResponse",
    "CompanySignalSummaryBase",
    "CompanySignalSummaryCreate",
    "CompanySignalSummaryResponse",
    "SignalCollectionRequest",
    "SignalCollectionResponse",
    "JobPosting",
    "TechnologyDetection",
    "Patent",
    # CS2 - Evidence
    "CompanyEvidence",
    "EvidenceStats",
    "BackfillRequest",
    "BackfillResponse",
    # CS3 - Evidence Mapper
    "DimensionMapping",
    "EvidenceScore",
    "DimensionScore",
    "SIGNAL_TO_DIMENSION_MAP",
]