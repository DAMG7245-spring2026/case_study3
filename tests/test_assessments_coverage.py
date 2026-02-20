"""Additional tests for app/routers/assessments.py to achieve ≥80% coverage."""
import pytest
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock


class TestListAssessments:
    """Tests for GET /api/v1/assessments."""

    def test_list_assessments_empty(self, client, mock_snowflake):
        """Test listing assessments returns empty paginated response."""
        mock_snowflake.execute_one.return_value = {"count": 0}
        mock_snowflake.execute_query.return_value = []

        with patch("app.routers.assessments.get_snowflake_service", return_value=mock_snowflake):
            response = client.get("/api/v1/assessments")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1

    def test_list_assessments_with_results(self, client, mock_snowflake):
        """Test listing assessments returns populated results."""
        now = datetime.now(timezone.utc)
        assessment_id = str(uuid4())
        company_id = str(uuid4())

        mock_snowflake.execute_one.return_value = {"count": 1}
        mock_snowflake.execute_query.return_value = [
            {
                "id": assessment_id,
                "company_id": company_id,
                "assessment_type": "screening",
                "assessment_date": now,
                "status": "draft",
                "h_r_score": None,
                "synergy": None,
                "v_r_score": None,
                "confidence_lower": None,
                "confidence_upper": None,
                "created_at": now,
            }
        ]

        with patch("app.routers.assessments.get_snowflake_service", return_value=mock_snowflake):
            response = client.get("/api/v1/assessments")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["status"] == "draft"

    def test_list_assessments_filter_company(self, client, mock_snowflake):
        """Test listing assessments filtered by company_id."""
        company_id = str(uuid4())
        mock_snowflake.execute_one.return_value = {"count": 0}
        mock_snowflake.execute_query.return_value = []

        with patch("app.routers.assessments.get_snowflake_service", return_value=mock_snowflake):
            response = client.get(f"/api/v1/assessments?company_id={company_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    def test_list_assessments_filter_status(self, client, mock_snowflake):
        """Test listing assessments filtered by status."""
        mock_snowflake.execute_one.return_value = {"count": 0}
        mock_snowflake.execute_query.return_value = []

        with patch("app.routers.assessments.get_snowflake_service", return_value=mock_snowflake):
            response = client.get("/api/v1/assessments?status=draft")

        assert response.status_code == 200

    def test_list_assessments_filter_type(self, client, mock_snowflake):
        """Test listing assessments filtered by assessment_type."""
        mock_snowflake.execute_one.return_value = {"count": 0}
        mock_snowflake.execute_query.return_value = []

        with patch("app.routers.assessments.get_snowflake_service", return_value=mock_snowflake):
            response = client.get("/api/v1/assessments?assessment_type=screening")

        assert response.status_code == 200

    def test_list_assessments_with_scores(self, client, mock_snowflake):
        """Test listing assessments with score values populated."""
        now = datetime.now(timezone.utc)
        mock_snowflake.execute_one.return_value = {"count": 1}
        mock_snowflake.execute_query.return_value = [
            {
                "id": str(uuid4()),
                "company_id": str(uuid4()),
                "assessment_type": "due_diligence",
                "assessment_date": now,
                "status": "approved",
                "h_r_score": 72.5,
                "synergy": 0.85,
                "v_r_score": 68.0,
                "confidence_lower": 63.0,
                "confidence_upper": 73.0,
                "created_at": now,
            }
        ]

        with patch("app.routers.assessments.get_snowflake_service", return_value=mock_snowflake):
            response = client.get("/api/v1/assessments")

        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["h_r_score"] == 72.5
        assert item["v_r_score"] == 68.0


class TestGetAssessment:
    """Tests for GET /api/v1/assessments/{id}."""

    def test_get_assessment_cache_miss_then_db(self, client, mock_snowflake, mock_redis):
        """Test get assessment with cache miss falls through to DB."""
        assessment_id = str(uuid4())
        now = datetime.now(timezone.utc)
        mock_redis.get.return_value = None  # Cache miss
        mock_snowflake.execute_one.return_value = {
            "id": assessment_id,
            "company_id": str(uuid4()),
            "assessment_type": "screening",
            "assessment_date": now,
            "status": "draft",
            "h_r_score": None,
            "synergy": None,
            "v_r_score": None,
            "confidence_lower": None,
            "confidence_upper": None,
            "created_at": now,
        }

        with patch("app.routers.assessments.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.assessments.get_redis_cache", return_value=mock_redis):
                response = client.get(f"/api/v1/assessments/{assessment_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "draft"

    def test_get_assessment_not_found(self, client, mock_snowflake, mock_redis):
        """Test get assessment returns 404 when not in DB."""
        mock_redis.get.return_value = None
        mock_snowflake.execute_one.return_value = None

        with patch("app.routers.assessments.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.assessments.get_redis_cache", return_value=mock_redis):
                response = client.get(f"/api/v1/assessments/{uuid4()}")

        assert response.status_code == 404

    def test_get_assessment_with_scores(self, client, mock_snowflake, mock_redis):
        """Test get assessment returns assessment with numeric scores."""
        assessment_id = str(uuid4())
        now = datetime.now(timezone.utc)
        mock_redis.get.return_value = None
        mock_snowflake.execute_one.return_value = {
            "id": assessment_id,
            "company_id": str(uuid4()),
            "assessment_type": "quarterly",
            "assessment_date": now,
            "status": "approved",
            "h_r_score": 70.0,
            "synergy": 0.9,
            "v_r_score": 75.0,
            "confidence_lower": 70.0,
            "confidence_upper": 80.0,
            "created_at": now,
        }

        with patch("app.routers.assessments.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.assessments.get_redis_cache", return_value=mock_redis):
                response = client.get(f"/api/v1/assessments/{assessment_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["v_r_score"] == 75.0
        assert data["h_r_score"] == 70.0


class TestUpdateAssessmentStatus:
    """Tests for PATCH /api/v1/assessments/{id}/status."""

    def test_update_status_not_found(self, client, mock_snowflake, mock_redis):
        """Test updating status of non-existent assessment returns 404."""
        mock_snowflake.execute_one.return_value = None

        with patch("app.routers.assessments.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.assessments.get_redis_cache", return_value=mock_redis):
                response = client.patch(
                    f"/api/v1/assessments/{uuid4()}/status",
                    json={"status": "in_progress"}
                )

        assert response.status_code == 404

    def test_valid_transition_draft_to_in_progress(self, client, mock_snowflake, mock_redis):
        """Test DRAFT → IN_PROGRESS is a valid transition."""
        assessment_id = str(uuid4())
        now = datetime.now(timezone.utc)
        mock_snowflake.execute_one.side_effect = [
            {"status": "draft"},
            {
                "id": assessment_id,
                "company_id": str(uuid4()),
                "assessment_type": "screening",
                "assessment_date": now,
                "status": "in_progress",
                "h_r_score": None,
                "synergy": None,
                "v_r_score": None,
                "confidence_lower": None,
                "confidence_upper": None,
                "created_at": now,
            }
        ]
        mock_redis.get.return_value = None

        with patch("app.routers.assessments.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.assessments.get_redis_cache", return_value=mock_redis):
                response = client.patch(
                    f"/api/v1/assessments/{assessment_id}/status",
                    json={"status": "in_progress"}
                )

        assert response.status_code == 200
        assert response.json()["status"] == "in_progress"

    def test_invalid_transition_draft_to_approved(self, client, mock_snowflake, mock_redis):
        """Test DRAFT → APPROVED is invalid."""
        mock_snowflake.execute_one.return_value = {"status": "draft"}

        with patch("app.routers.assessments.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.assessments.get_redis_cache", return_value=mock_redis):
                response = client.patch(
                    f"/api/v1/assessments/{uuid4()}/status",
                    json={"status": "approved"}
                )

        assert response.status_code == 400
        assert "Invalid status transition" in response.json()["detail"]

    def test_valid_transition_in_progress_to_submitted(self, client, mock_snowflake, mock_redis):
        """Test IN_PROGRESS → SUBMITTED is a valid transition."""
        assessment_id = str(uuid4())
        now = datetime.now(timezone.utc)
        mock_snowflake.execute_one.side_effect = [
            {"status": "in_progress"},
            {
                "id": assessment_id,
                "company_id": str(uuid4()),
                "assessment_type": "screening",
                "assessment_date": now,
                "status": "submitted",
                "h_r_score": None,
                "synergy": None,
                "v_r_score": None,
                "confidence_lower": None,
                "confidence_upper": None,
                "created_at": now,
            }
        ]
        mock_redis.get.return_value = None

        with patch("app.routers.assessments.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.assessments.get_redis_cache", return_value=mock_redis):
                response = client.patch(
                    f"/api/v1/assessments/{assessment_id}/status",
                    json={"status": "submitted"}
                )

        assert response.status_code == 200


class TestDimensionScoresViaAssessment:
    """Tests for GET /api/v1/assessments/{id}/scores."""

    def test_get_dimension_scores_not_found(self, client, mock_snowflake):
        """Test get dimension scores returns 404 when assessment not found."""
        mock_snowflake.execute_one.return_value = None

        with patch("app.routers.assessments.get_snowflake_service", return_value=mock_snowflake):
            response = client.get(f"/api/v1/assessments/{uuid4()}/scores")

        assert response.status_code == 404

    def test_get_dimension_scores_empty(self, client, mock_snowflake):
        """Test get dimension scores returns empty list."""
        assessment_id = str(uuid4())
        company_id = str(uuid4())
        mock_snowflake.execute_one.return_value = {
            "id": assessment_id,
            "company_id": company_id,
        }
        mock_snowflake.execute_query.return_value = []

        with patch("app.routers.assessments.get_snowflake_service", return_value=mock_snowflake):
            response = client.get(f"/api/v1/assessments/{assessment_id}/scores")

        assert response.status_code == 200
        assert response.json() == []

    def test_get_dimension_scores_with_data(self, client, mock_snowflake):
        """Test get dimension scores returns actual scores."""
        assessment_id = str(uuid4())
        company_id = str(uuid4())
        score_id = str(uuid4())
        now = datetime.now(timezone.utc)

        mock_snowflake.execute_one.return_value = {
            "id": assessment_id,
            "company_id": company_id,
        }
        mock_snowflake.execute_query.return_value = [
            {
                "id": score_id,
                "company_id": company_id,
                "dimension": "data_infrastructure",
                "score": 75.0,
                "total_weight": 0.25,
                "confidence": 0.85,
                "evidence_count": 5,
                "contributing_sources": None,
                "created_at": now,
            }
        ]

        with patch("app.routers.assessments.get_snowflake_service", return_value=mock_snowflake):
            response = client.get(f"/api/v1/assessments/{assessment_id}/scores")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["dimension"] == "data_infrastructure"
        assert data[0]["score"] == 75.0

    def test_add_dimension_scores_assessment_not_found(self, client, mock_snowflake, mock_redis):
        """Test adding scores when assessment doesn't exist returns 404."""
        mock_snowflake.execute_one.return_value = None

        with patch("app.routers.assessments.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.assessments.get_redis_cache", return_value=mock_redis):
                response = client.post(
                    f"/api/v1/assessments/{uuid4()}/scores",
                    json={
                        "scores": [{
                            "company_id": str(uuid4()),
                            "dimension": "data_infrastructure",
                            "score": 75.0
                        }]
                    }
                )

        assert response.status_code == 404
