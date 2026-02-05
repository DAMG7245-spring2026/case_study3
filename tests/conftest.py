"""Pytest fixtures and configuration."""
import pytest
from uuid import uuid4
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch
import fakeredis


@pytest.fixture
def mock_snowflake():
    """Mock Snowflake service."""
    mock = MagicMock()
    mock.health_check = AsyncMock(return_value=(True, None))
    mock.execute_query = MagicMock(return_value=[])
    mock.execute_one = MagicMock(return_value=None)
    mock.execute_write = MagicMock(return_value=1)
    return mock


@pytest.fixture
def mock_redis():
    """Mock Redis service using fakeredis."""
    mock = MagicMock()
    mock.health_check = AsyncMock(return_value=(True, None))
    mock.get = MagicMock(return_value=None)
    mock.set = MagicMock(return_value=True)
    mock.delete = MagicMock(return_value=True)
    return mock


@pytest.fixture
def mock_s3():
    """Mock S3 service."""
    mock = MagicMock()
    mock.health_check = AsyncMock(return_value=(True, None))
    return mock


@pytest.fixture
def client(mock_snowflake, mock_redis, mock_s3):
    """Create test client with mocked services."""
    with patch("app.routers.health.get_snowflake_service", return_value=mock_snowflake):
        with patch("app.routers.health.get_redis_cache", return_value=mock_redis):
            with patch("app.routers.health.get_s3_storage", return_value=mock_s3):
                from app.main import app
                yield TestClient(app)


@pytest.fixture
def sample_industry_id():
    """Sample industry UUID."""
    return "550e8400-e29b-41d4-a716-446655440001"


@pytest.fixture
def sample_company_id():
    """Sample company UUID."""
    return str(uuid4())


@pytest.fixture
def sample_assessment_id():
    """Sample assessment UUID."""
    return str(uuid4())


@pytest.fixture
def sample_company_data(sample_industry_id):
    """Sample company creation data."""
    return {
        "name": "Test Company Inc.",
        "ticker": "TEST",
        "industry_id": sample_industry_id,
        "position_factor": 0.5
    }


@pytest.fixture
def sample_assessment_data(sample_company_id):
    """Sample assessment creation data."""
    return {
        "company_id": sample_company_id,
        "assessment_type": "screening",
        "primary_assessor": "John Doe"
    }


@pytest.fixture
def sample_dimension_scores(sample_assessment_id):
    """Sample dimension scores data."""
    return {
        "scores": [
            {
                "assessment_id": sample_assessment_id,
                "dimension": "data_infrastructure",
                "score": 75.5,
                "confidence": 0.85,
                "evidence_count": 5
            },
            {
                "assessment_id": sample_assessment_id,
                "dimension": "ai_governance",
                "score": 68.0,
                "confidence": 0.80,
                "evidence_count": 3
            }
        ]
    }