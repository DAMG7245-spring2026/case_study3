import pytest
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.snowflake import get_snowflake_service
from app.services.s3_storage import get_s3_storage


@pytest.fixture
def override_snowflake(mock_snowflake, mock_s3):
    """Override snowflake and s3 service dependencies globally."""
    app.dependency_overrides[get_snowflake_service] = lambda: mock_snowflake
    app.dependency_overrides[get_s3_storage] = lambda: mock_s3
    yield mock_snowflake
    app.dependency_overrides.clear()


class TestDocumentEndpoints:
    """Tests for document collection and retrieval."""

    def test_collect_documents_endpoint(self, client, override_snowflake):
        """Test document collection trigger returns queued status."""
        company_id = str(uuid4())
        request_data = {
            "company_id": company_id,
            "filing_types": ["10-K"],
            "years_back": 1
        }

        response = client.post("/api/v1/documents/collect", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "queued"

    def test_list_documents(self, client, override_snowflake):
        """Test listing documents uses get_documents and count_documents."""
        company_id = str(uuid4())
        doc_id = str(uuid4())
        now = datetime.now(timezone.utc)

        override_snowflake.get_documents.return_value = [
            {
                "id": doc_id,
                "company_id": company_id,
                "ticker": "AAPL",
                "filing_type": "10-K",
                "filing_date": now,
                "status": "parsed",
                "s3_key": None,
                "content_hash": None,
                "word_count": 1000,
                "local_path": None,
                "source_url": None,
                "chunk_count": None,
                "error_message": None,
                "created_at": now,
                "processed_at": None,
            }
        ]
        override_snowflake.count_documents.return_value = 1

        response = client.get(f"/api/v1/documents?company_id={company_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["ticker"] == "AAPL"


class TestSignalEndpoints:
    """Tests for external signal endpoints."""

    def test_collect_signals_endpoint(self, client, override_snowflake):
        """Test signal collection trigger returns queued status."""
        company_id = str(uuid4())

        response = client.post("/api/v1/signals/collect", json={"company_id": company_id})

        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "queued"

    def test_get_signal_summary(self, client, override_snowflake):
        """Test getting signal summary for a company."""
        company_id = uuid4()
        now = datetime.now(timezone.utc)

        override_snowflake.get_signal_summary.return_value = {
            "company_id": str(company_id),
            "ticker": "AAPL",
            "technology_hiring_score": 80.0,
            "innovation_activity_score": 75.0,
            "digital_presence_score": 85.0,
            "leadership_signals_score": 70.0,
            "composite_score": 78.0,
            "signal_count": 10,
            "last_updated": now,
        }

        response = client.get(f"/api/v1/companies/{company_id}/signals")

        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "AAPL"


class TestEvidenceEndpoints:
    """Tests for unified evidence endpoints."""

    def test_get_company_evidence(self, client, override_snowflake):
        """Test getting all evidence for a company."""
        company_id = uuid4()
        doc_id = str(uuid4())
        now = datetime.now(timezone.utc)

        override_snowflake.get_documents.return_value = [
            {
                "id": doc_id,
                "company_id": str(company_id),
                "ticker": "AAPL",
                "filing_type": "10-K",
                "filing_date": now,
                "status": "parsed",
                "s3_key": None,
                "content_hash": None,
                "word_count": 1000,
                "local_path": None,
                "source_url": None,
                "chunk_count": None,
                "error_message": None,
                "created_at": now,
                "processed_at": None,
            }
        ]
        override_snowflake.count_chunks.return_value = 5
        override_snowflake.get_signals.return_value = [
            {
                "id": str(uuid4()),
                "company_id": str(company_id),
                "category": "technology_hiring",
                "source": "indeed",
                "signal_date": now,
                "raw_value": "10 jobs",
                "normalized_score": 80.0,
                "confidence": 0.9,
                "metadata": {},
                "created_at": now,
            }
        ]
        override_snowflake.get_signal_summary.return_value = {
            "company_id": str(company_id),
            "ticker": "AAPL",
            "technology_hiring_score": 80.0,
            "innovation_activity_score": 75.0,
            "digital_presence_score": 85.0,
            "leadership_signals_score": 70.0,
            "composite_score": 75.0,
            "signal_count": 1,
            "last_updated": now,
        }
        override_snowflake.get_company_by_id.return_value = {
            "id": str(company_id),
            "name": "Apple Inc.",
            "ticker": "AAPL",
        }

        response = client.get(f"/api/v1/companies/{company_id}/evidence")

        assert response.status_code == 200
        data = response.json()
        assert data["document_count"] == 1
        assert len(data["signals"]) == 1
        assert data["signal_summary"]["ticker"] == "AAPL"
