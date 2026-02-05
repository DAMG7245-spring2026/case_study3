"""Tests for Pydantic models."""
import pytest
from uuid import uuid4
from datetime import datetime, timezone
from pydantic import ValidationError
from app.models import (
    CompanyCreate, CompanyResponse, CompanyUpdate,
    AssessmentCreate, AssessmentResponse, AssessmentStatus, AssessmentType,
    DimensionScoreCreate, DimensionScoreResponse, Dimension, DIMENSION_WEIGHTS
)


class TestCompanyModels:
    """Tests for Company models."""
    
    def test_company_create_valid(self):
        """Test valid company creation."""
        company = CompanyCreate(
            name="Test Company",
            ticker="TEST",
            industry_id=uuid4(),
            position_factor=0.5
        )
        assert company.name == "Test Company"
        assert company.ticker == "TEST"
        assert company.position_factor == 0.5
    
    def test_company_create_ticker_uppercase(self):
        """Test ticker is converted to uppercase."""
        company = CompanyCreate(
            name="Test Company",
            ticker="test",
            industry_id=uuid4()
        )
        assert company.ticker == "TEST"
    
    def test_company_create_optional_ticker(self):
        """Test company can be created without ticker."""
        company = CompanyCreate(
            name="Private Company",
            industry_id=uuid4()
        )
        assert company.ticker is None
    
    def test_company_create_default_position_factor(self):
        """Test default position factor is 0.0."""
        company = CompanyCreate(
            name="Test Company",
            industry_id=uuid4()
        )
        assert company.position_factor == 0.0
    
    def test_company_create_invalid_name_empty(self):
        """Test validation error for empty name."""
        with pytest.raises(ValidationError) as exc_info:
            CompanyCreate(name="", industry_id=uuid4())
        # Check for the error type instead of specific string
        assert "string_too_short" in str(exc_info.value)
    
    def test_company_create_invalid_position_factor(self):
        """Test validation error for out-of-range position factor."""
        with pytest.raises(ValidationError):
            CompanyCreate(
                name="Test",
                industry_id=uuid4(),
                position_factor=1.5  # Max is 1.0
            )
    
    def test_company_update_partial(self):
        """Test partial update model."""
        update = CompanyUpdate(name="New Name")
        assert update.name == "New Name"
        assert update.ticker is None
        assert update.industry_id is None


class TestAssessmentModels:
    """Tests for Assessment models."""
    
    def test_assessment_create_valid(self):
        """Test valid assessment creation."""
        company_id = uuid4()
        assessment = AssessmentCreate(
            company_id=company_id,
            assessment_type=AssessmentType.SCREENING,
            primary_assessor="John Doe"
        )
        assert assessment.company_id == company_id
        assert assessment.assessment_type == AssessmentType.SCREENING
        assert assessment.primary_assessor == "John Doe"
    
    def test_assessment_create_default_date(self):
        """Test default assessment date is set."""
        assessment = AssessmentCreate(
            company_id=uuid4(),
            assessment_type=AssessmentType.DUE_DILIGENCE
        )
        assert assessment.assessment_date is not None
    
    def test_assessment_response_confidence_interval_valid(self):
        """Test valid confidence interval."""
        response = AssessmentResponse(
            id=uuid4(),
            company_id=uuid4(),
            assessment_type=AssessmentType.SCREENING,
            assessment_date=datetime.now(timezone.utc),
            status=AssessmentStatus.APPROVED,
            v_r_score=75.0,
            confidence_lower=70.0,
            confidence_upper=80.0,
            created_at=datetime.now(timezone.utc)
        )
        assert response.confidence_lower < response.confidence_upper
    
    def test_assessment_response_invalid_confidence_interval(self):
        """Test validation error when upper < lower."""
        with pytest.raises(ValidationError) as exc_info:
            AssessmentResponse(
                id=uuid4(),
                company_id=uuid4(),
                assessment_type=AssessmentType.SCREENING,
                assessment_date=datetime.now(timezone.utc),
                status=AssessmentStatus.APPROVED,
                confidence_lower=80.0,
                confidence_upper=70.0,  # Invalid: lower > upper
                created_at=datetime.now(timezone.utc)
            )
        assert "confidence_upper must be >= confidence_lower" in str(exc_info.value)
    
    def test_assessment_types(self):
        """Test all assessment types are valid."""
        types = [
            AssessmentType.SCREENING,
            AssessmentType.DUE_DILIGENCE,
            AssessmentType.QUARTERLY,
            AssessmentType.EXIT_PREP
        ]
        for t in types:
            assessment = AssessmentCreate(
                company_id=uuid4(),
                assessment_type=t
            )
            assert assessment.assessment_type == t


class TestDimensionScoreModels:
    """Tests for Dimension Score models."""
    
    def test_dimension_score_valid(self):
        """Test valid dimension score creation."""
        score = DimensionScoreCreate(
            assessment_id=uuid4(),
            dimension=Dimension.DATA_INFRASTRUCTURE,
            score=85.5,
            confidence=0.9,
            evidence_count=10
        )
        assert score.score == 85.5
        assert score.dimension == Dimension.DATA_INFRASTRUCTURE
    
    def test_dimension_score_default_weight(self):
        """Test default weight is set based on dimension."""
        score = DimensionScoreCreate(
            assessment_id=uuid4(),
            dimension=Dimension.DATA_INFRASTRUCTURE,
            score=75.0
        )
        assert score.weight == DIMENSION_WEIGHTS[Dimension.DATA_INFRASTRUCTURE]
        assert score.weight == 0.25
    
    def test_dimension_score_custom_weight(self):
        """Test custom weight overrides default."""
        score = DimensionScoreCreate(
            assessment_id=uuid4(),
            dimension=Dimension.DATA_INFRASTRUCTURE,
            score=75.0,
            weight=0.30
        )
        assert score.weight == 0.30
    
    def test_dimension_score_invalid_score_range(self):
        """Test validation error for out-of-range score."""
        with pytest.raises(ValidationError):
            DimensionScoreCreate(
                assessment_id=uuid4(),
                dimension=Dimension.AI_GOVERNANCE,
                score=105.0  # Max is 100
            )
    
    def test_dimension_score_invalid_confidence(self):
        """Test validation error for out-of-range confidence."""
        with pytest.raises(ValidationError):
            DimensionScoreCreate(
                assessment_id=uuid4(),
                dimension=Dimension.AI_GOVERNANCE,
                score=75.0,
                confidence=1.5  # Max is 1.0
            )
    
    def test_all_dimensions_have_weights(self):
        """Test all dimensions have default weights."""
        for dim in Dimension:
            assert dim in DIMENSION_WEIGHTS
        # Weights should sum to 1.0
        total_weight = sum(DIMENSION_WEIGHTS.values())
        assert abs(total_weight - 1.0) < 0.001