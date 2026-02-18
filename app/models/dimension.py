"""Dimension Score Pydantic models."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, model_validator, ConfigDict
from .enums import Dimension, DIMENSION_WEIGHTS


class DimensionScoreBase(BaseModel):
    """Base dimension score model."""
    company_id: UUID
    dimension: Dimension
    score: float = Field(..., ge=0, le=100, description="Score from 0-100")
    total_weight: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description="Weight for this dimension (0-1)"
    )
    confidence: float = Field(
        default=0.8,
        ge=0,
        le=1,
        description="Confidence level (0-1)"
    )
    evidence_count: int = Field(
        default=0,
        ge=0,
        description="Number of evidence pieces supporting this score"
    )
    contributing_sources: Optional[List[str]] = Field(
        default=None,
        description="Signal sources that contributed to this score"
    )

    @model_validator(mode="after")
    def set_default_weight(self) -> "DimensionScoreBase":
        """Set default weight based on dimension if not provided."""
        if self.total_weight is None:
            self.total_weight = DIMENSION_WEIGHTS.get(self.dimension, 0.1)
        return self


class DimensionScoreCreate(DimensionScoreBase):
    """Model for creating a dimension score."""
    pass


class DimensionScoreBulkCreate(BaseModel):
    """Model for creating multiple dimension scores at once."""
    scores: list[DimensionScoreCreate]


class DimensionScoreUpdate(BaseModel):
    """Model for updating a dimension score."""
    score: Optional[float] = Field(None, ge=0, le=100)
    total_weight: Optional[float] = Field(None, ge=0, le=1)
    confidence: Optional[float] = Field(None, ge=0, le=1)
    evidence_count: Optional[int] = Field(None, ge=0)
    contributing_sources: Optional[List[str]] = None


class DimensionScoreResponse(DimensionScoreBase):
    """Dimension score response model."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    created_at: datetime


class DimensionScoreSummary(BaseModel):
    """Summary of dimension scores for a company."""
    company_id: UUID
    total_dimensions: int
    scored_dimensions: int
    weighted_average: Optional[float] = None
    min_score: Optional[float] = None
    max_score: Optional[float] = None
    scores: list[DimensionScoreResponse]