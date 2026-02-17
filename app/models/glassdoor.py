"""Glassdoor review models for culture signal collection (raw data only)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class GlassdoorReview(BaseModel):
    """A single Glassdoor review (for parsing/validation only)."""

    review_id: str
    rating: float = Field(..., ge=1, le=5)
    title: str = ""
    pros: str = ""
    cons: str = ""
    advice_to_management: Optional[str] = None
    is_current_employee: bool = False
    job_title: str = ""
    review_date: datetime

    @field_validator("review_date", mode="before")
    @classmethod
    def parse_review_date(cls, v: object) -> datetime:
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                pass
        raise ValueError("review_date must be datetime or ISO format string")
