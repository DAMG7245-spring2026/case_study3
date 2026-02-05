"""Tests for API endpoints."""
import pytest
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock


class TestHealthEndpoint:
    """Tests for health check endpoint."""
    
    def test_health_check_all_healthy(self, client, mock_snowflake, mock_redis, mock_s3):
        """Test health check returns 200 when all dependencies healthy."""
        mock_snowflake.health_check = AsyncMock(return_value=(True, None))
        mock_redis.health_check = AsyncMock(return_value=(True, None))
        mock_s3.health_check = AsyncMock(return_value=(True, None))
        
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data
        assert "dependencies" in data
    
    def test_health_check_degraded(self, client, mock_snowflake, mock_redis, mock_s3):
        """Test health check returns 503 when any dependency unhealthy."""
        mock_snowflake.health_check = AsyncMock(return_value=(False, "Connection failed"))
        mock_redis.health_check = AsyncMock(return_value=(True, None))
        mock_s3.health_check = AsyncMock(return_value=(True, None))
        
        response = client.get("/health")
        
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"


class TestCompanyEndpoints:
    """Tests for company CRUD endpoints."""
    
    def test_create_company_success(self, client, mock_snowflake, sample_company_data):
        """Test successful company creation."""
        # Mock industry exists check
        mock_snowflake.execute_one.return_value = {"id": sample_company_data["industry_id"]}
        mock_snowflake.execute_write.return_value = 1
        
        with patch("app.routers.companies.get_snowflake_service", return_value=mock_snowflake):
            response = client.post("/api/v1/companies", json=sample_company_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_company_data["name"]
        assert data["ticker"] == sample_company_data["ticker"]
        assert "id" in data
    
    def test_create_company_invalid_industry(self, client, mock_snowflake, sample_company_data):
        """Test company creation fails with invalid industry."""
        mock_snowflake.execute_one.return_value = None  # Industry not found
        
        with patch("app.routers.companies.get_snowflake_service", return_value=mock_snowflake):
            response = client.post("/api/v1/companies", json=sample_company_data)
        
        assert response.status_code == 400
        assert "not found" in response.json()["detail"]
    
    def test_list_companies_empty(self, client, mock_snowflake):
        """Test listing companies returns empty list."""
        mock_snowflake.execute_one.return_value = {"count": 0}
        mock_snowflake.execute_query.return_value = []
        
        with patch("app.routers.companies.get_snowflake_service", return_value=mock_snowflake):
            response = client.get("/api/v1/companies")
        
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
    
    def test_list_companies_with_pagination(self, client, mock_snowflake):
        """Test listing companies with custom pagination."""
        mock_snowflake.execute_one.return_value = {"count": 50}
        mock_snowflake.execute_query.return_value = []
        
        with patch("app.routers.companies.get_snowflake_service", return_value=mock_snowflake):
            response = client.get("/api/v1/companies?page=2&page_size=10")
        
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 10
        assert data["total_pages"] == 5
    
    def test_get_company_not_found(self, client, mock_snowflake, mock_redis):
        """Test getting non-existent company returns 404."""
        mock_redis.get.return_value = None
        mock_snowflake.execute_one.return_value = None
        
        company_id = str(uuid4())
        with patch("app.routers.companies.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.companies.get_redis_cache", return_value=mock_redis):
                response = client.get(f"/api/v1/companies/{company_id}")
        
        assert response.status_code == 404
    
    def test_delete_company_success(self, client, mock_snowflake, mock_redis):
        """Test soft deleting a company."""
        company_id = str(uuid4())
        mock_snowflake.execute_one.return_value = {"id": company_id}
        mock_snowflake.execute_write.return_value = 1
        
        with patch("app.routers.companies.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.companies.get_redis_cache", return_value=mock_redis):
                response = client.delete(f"/api/v1/companies/{company_id}")
        
        assert response.status_code == 200
        assert "deleted successfully" in response.json()["message"]


class TestAssessmentEndpoints:
    """Tests for assessment endpoints."""
    
    def test_create_assessment_success(self, client, mock_snowflake, sample_assessment_data):
        """Test successful assessment creation."""
        mock_snowflake.execute_one.return_value = {"id": sample_assessment_data["company_id"]}
        mock_snowflake.execute_write.return_value = 1
        
        with patch("app.routers.assessments.get_snowflake_service", return_value=mock_snowflake):
            response = client.post("/api/v1/assessments", json=sample_assessment_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["assessment_type"] == "screening"
        assert data["status"] == "draft"
    
    def test_update_assessment_status_valid_transition(self, client, mock_snowflake, mock_redis):
        """Test valid status transition."""
        assessment_id = str(uuid4())
        mock_snowflake.execute_one.side_effect = [
            {"status": "draft"},  # Current status
            {  # Updated assessment
                "id": assessment_id,
                "company_id": str(uuid4()),
                "assessment_type": "screening",
                "assessment_date": datetime.now(timezone.utc),
                "status": "in_progress",
                "primary_assessor": None,
                "secondary_assessor": None,
                "v_r_score": None,
                "confidence_lower": None,
                "confidence_upper": None,
                "created_at": datetime.now(timezone.utc)
            }
        ]
        
        with patch("app.routers.assessments.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.assessments.get_redis_cache", return_value=mock_redis):
                response = client.patch(
                    f"/api/v1/assessments/{assessment_id}/status",
                    json={"status": "in_progress"}
                )
        
        assert response.status_code == 200
    
    def test_update_assessment_status_invalid_transition(self, client, mock_snowflake, mock_redis):
        """Test invalid status transition fails."""
        assessment_id = str(uuid4())
        # Return the same value for all calls - assessment exists with draft status
        mock_snowflake.execute_one.return_value = {"status": "draft"}
        mock_snowflake.execute_write.return_value = 0
        
        with patch("app.routers.assessments.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.assessments.get_redis_cache", return_value=mock_redis):
                response = client.patch(
                    f"/api/v1/assessments/{assessment_id}/status",
                    json={"status": "approved"}  # Can't go from draft to approved
                )
        
        assert response.status_code == 400
        assert "Invalid status transition" in response.json()["detail"]


class TestDimensionScoreEndpoints:
    """Tests for dimension score endpoints."""
    
    def test_add_dimension_scores_success(
        self, client, mock_snowflake, mock_redis, sample_dimension_scores
    ):
        """Test adding dimension scores to assessment."""
        assessment_id = str(uuid4())
        mock_snowflake.execute_one.side_effect = [
            {"id": assessment_id},  # Assessment exists
            None, None  # No existing scores for dimensions
        ]
        mock_snowflake.execute_write.return_value = 1
        
        with patch("app.routers.assessments.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.assessments.get_redis_cache", return_value=mock_redis):
                response = client.post(
                    f"/api/v1/assessments/{assessment_id}/scores",
                    json=sample_dimension_scores
                )
        
        assert response.status_code == 201
        data = response.json()
        assert len(data) == 2
    
    def test_add_duplicate_dimension_score_fails(
        self, client, mock_snowflake, mock_redis
    ):
        """Test adding duplicate dimension score fails."""
        assessment_id = str(uuid4())
        mock_snowflake.execute_one.side_effect = [
            {"id": assessment_id},  # Assessment exists
            {"id": str(uuid4())}  # Score already exists
        ]
        
        with patch("app.routers.assessments.get_snowflake_service", return_value=mock_snowflake):
            response = client.post(
                f"/api/v1/assessments/{assessment_id}/scores",
                json={
                    "scores": [{
                        "assessment_id": assessment_id,
                        "dimension": "data_infrastructure",
                        "score": 75.0
                    }]
                }
            )
        
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]