"""Assessment Pydantic models."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING, List
from uuid import UUID
from pydantic import BaseModel, Field, model_validator, ConfigDict
from .enums import AssessmentType, AssessmentStatus

if TYPE_CHECKING:
    from .dimension import DimensionScoreResponse


class AssessmentBase(BaseModel):
    """Base assessment model."""
    company_id: UUID
    assessment_type: AssessmentType
    assessment_date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class AssessmentCreate(AssessmentBase):
    """Model for creating an assessment."""
    pass


class AssessmentUpdate(BaseModel):
    """Model for updating an assessment."""
    assessment_type: Optional[AssessmentType] = None
    assessment_date: Optional[datetime] = None
    h_r_score: Optional[float] = None
    synergy: Optional[float] = None
    v_r_score: Optional[float] = Field(None, ge=0, le=100)
    confidence_lower: Optional[float] = Field(None, ge=0, le=100)
    confidence_upper: Optional[float] = Field(None, ge=0, le=100)
    
    @model_validator(mode="after")
    def validate_confidence_interval(self) -> "AssessmentUpdate":
        """Ensure confidence_upper >= confidence_lower."""
        if (
            self.confidence_upper is not None
            and self.confidence_lower is not None
            and self.confidence_upper < self.confidence_lower
        ):
            raise ValueError("confidence_upper must be >= confidence_lower")
        return self


class AssessmentStatusUpdate(BaseModel):
    """Model for updating assessment status."""
    status: AssessmentStatus


class AssessmentResponse(AssessmentBase):
    """Assessment response model with computed fields."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    status: AssessmentStatus = AssessmentStatus.DRAFT
    h_r_score: Optional[float] = None
    synergy: Optional[float] = None
    v_r_score: Optional[float] = Field(None, ge=0, le=100)
    confidence_lower: Optional[float] = Field(None, ge=0, le=100)
    confidence_upper: Optional[float] = Field(None, ge=0, le=100)
    created_at: datetime
    
    @model_validator(mode="after")
    def validate_confidence_interval(self) -> "AssessmentResponse":
        """Ensure confidence_upper >= confidence_lower."""
        if (
            self.confidence_upper is not None
            and self.confidence_lower is not None
            and self.confidence_upper < self.confidence_lower
        ):
            raise ValueError("confidence_upper must be >= confidence_lower")
        return self


class AssessmentWithScores(AssessmentResponse):
    """Assessment response including dimension scores."""
    dimension_scores: List = Field(default_factory=list)