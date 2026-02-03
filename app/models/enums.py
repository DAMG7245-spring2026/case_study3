"""Enumeration types for the PE Org-AI-R platform."""
from enum import Enum


class AssessmentType(str, Enum):
    """Types of AI-readiness assessments."""
    SCREENING = "screening"  # Quick external assessment
    DUE_DILIGENCE = "due_diligence"  # Deep dive with internal access
    QUARTERLY = "quarterly"  # Regular portfolio monitoring
    EXIT_PREP = "exit_prep"  # Pre-exit assessment


class AssessmentStatus(str, Enum):
    """Status states for assessments."""
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


class Dimension(str, Enum):
    """The seven dimensions of AI-readiness."""
    DATA_INFRASTRUCTURE = "data_infrastructure"
    AI_GOVERNANCE = "ai_governance"
    TECHNOLOGY_STACK = "technology_stack"
    TALENT_SKILLS = "talent_skills"
    LEADERSHIP_VISION = "leadership_vision"
    USE_CASE_PORTFOLIO = "use_case_portfolio"
    CULTURE_CHANGE = "culture_change"


# Default weights per dimension (must sum to 1.0)
DIMENSION_WEIGHTS: dict[Dimension, float] = {
    Dimension.DATA_INFRASTRUCTURE: 0.25,
    Dimension.AI_GOVERNANCE: 0.20,
    Dimension.TECHNOLOGY_STACK: 0.15,
    Dimension.TALENT_SKILLS: 0.15,
    Dimension.LEADERSHIP_VISION: 0.10,
    Dimension.USE_CASE_PORTFOLIO: 0.10,
    Dimension.CULTURE_CHANGE: 0.05,
}


# Valid status transitions
VALID_STATUS_TRANSITIONS: dict[AssessmentStatus, list[AssessmentStatus]] = {
    AssessmentStatus.DRAFT: [AssessmentStatus.IN_PROGRESS],
    AssessmentStatus.IN_PROGRESS: [AssessmentStatus.SUBMITTED, AssessmentStatus.DRAFT],
    AssessmentStatus.SUBMITTED: [AssessmentStatus.APPROVED, AssessmentStatus.IN_PROGRESS],
    AssessmentStatus.APPROVED: [AssessmentStatus.SUPERSEDED],
    AssessmentStatus.SUPERSEDED: [],
}