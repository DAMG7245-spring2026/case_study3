"""Assessment ORM model."""
from sqlalchemy import String, Float, Numeric, Date, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from datetime import datetime, date
import uuid

from app.database.base import Base


class Assessment(Base):
    """Assessment record table."""
    __tablename__ = "assessments"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    # Fields
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"))
    assessment_date: Mapped[date] = mapped_column(Date)
    h_r_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    synergy: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    v_r_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    org_ai_r: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    confidence_lower: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence_upper: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    # Relationships
    company: Mapped["Company"] = relationship(
        "Company",
        back_populates="assessments"
    )

    # Note: Snowflake doesn't support CHECK constraints
    # Validation is handled at the application layer (Pydantic models)

    def __repr__(self):
        return f"<Assessment(id={self.id}, company_id={self.company_id})>"
