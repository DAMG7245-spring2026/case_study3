"""Company and Industry Pydantic models."""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, field_validator, ConfigDict


class IndustryBase(BaseModel):
    """Base industry model."""
    name: str = Field(..., min_length=1, max_length=255)
    sector: str = Field(..., min_length=1, max_length=100)
    h_r_base: float = Field(..., ge=0, le=100, description="Base HR score for industry")


class IndustryCreate(IndustryBase):
    """Model for creating an industry."""
    pass


class IndustryResponse(IndustryBase):
    """Industry response model with ID and timestamps."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    created_at: datetime


class CompanyBase(BaseModel):
    """Base company model with validation."""
    name: str = Field(..., min_length=1, max_length=255)
    ticker: Optional[str] = Field(None, max_length=10)
    industry_id: UUID
    position_factor: float = Field(
        default=0.0, 
        ge=-1.0, 
        le=1.0,
        description="Market position factor (-1.0 to 1.0)"
    )
    
    @field_validator("ticker")
    @classmethod
    def uppercase_ticker(cls, v: Optional[str]) -> Optional[str]:
        """Convert ticker to uppercase."""
        return v.upper() if v else None


class CompanyCreate(CompanyBase):
    """Model for creating a company."""
    pass


class CompanyUpdate(BaseModel):
    """Model for updating a company (all fields optional)."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    ticker: Optional[str] = Field(None, max_length=10)
    industry_id: Optional[UUID] = None
    position_factor: Optional[float] = Field(None, ge=-1.0, le=1.0)
    
    @field_validator("ticker")
    @classmethod
    def uppercase_ticker(cls, v: Optional[str]) -> Optional[str]:
        """Convert ticker to uppercase."""
        return v.upper() if v else None


class CompanyResponse(CompanyBase):
    """Company response model with ID and timestamps."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    created_at: datetime
    updated_at: datetime


class CompanyWithIndustry(CompanyResponse):
    """Company response including industry details."""
    industry: Optional[IndustryResponse] = None