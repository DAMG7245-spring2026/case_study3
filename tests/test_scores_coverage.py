"""Additional tests for app/routers/scores.py to achieve ≥80% coverage."""
import pytest
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_score_row(company_id=None, dimension="data_infrastructure"):
    """Return a minimal dimension_score row dict."""
    now = datetime.now(timezone.utc)
    return {
        "id": str(uuid4()),
        "company_id": str(company_id or uuid4()),
        "dimension": dimension,
        "score": 75.0,
        "total_weight": 0.25,
        "confidence": 0.85,
        "evidence_count": 5,
        "contributing_sources": None,
        "created_at": now,
    }


# ---------------------------------------------------------------------------
# PUT /api/v1/scores/{score_id}
# ---------------------------------------------------------------------------

class TestUpdateDimensionScore:
    """Tests for PUT /api/v1/scores/{score_id}."""

    def test_update_score_success(self, client, mock_snowflake, mock_redis):
        """Test updating a dimension score returns 200 with updated data."""
        score_id = str(uuid4())
        company_id = str(uuid4())
        now = datetime.now(timezone.utc)

        original_row = _make_score_row(company_id=company_id)
        original_row["id"] = score_id

        updated_row = dict(original_row)
        updated_row["score"] = 80.0

        mock_snowflake.execute_one.side_effect = [original_row, updated_row]
        mock_snowflake.execute_write.return_value = 1

        with patch("app.routers.scores.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.scores.get_redis_cache", return_value=mock_redis):
                response = client.put(
                    f"/api/v1/scores/{score_id}",
                    json={"score": 80.0}
                )

        assert response.status_code == 200
        data = response.json()
        assert data["score"] == 80.0

    def test_update_score_not_found(self, client, mock_snowflake, mock_redis):
        """Test updating a non-existent score returns 404."""
        mock_snowflake.execute_one.return_value = None

        with patch("app.routers.scores.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.scores.get_redis_cache", return_value=mock_redis):
                response = client.put(
                    f"/api/v1/scores/{uuid4()}",
                    json={"score": 80.0}
                )

        assert response.status_code == 404

    def test_update_score_no_fields(self, client, mock_snowflake, mock_redis):
        """Test updating with no valid fields returns 400."""
        score_id = str(uuid4())
        mock_snowflake.execute_one.return_value = _make_score_row()

        with patch("app.routers.scores.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.scores.get_redis_cache", return_value=mock_redis):
                response = client.put(
                    f"/api/v1/scores/{score_id}",
                    json={}
                )

        assert response.status_code == 400
        assert "No fields to update" in response.json()["detail"]

    def test_update_score_with_json_sources(self, client, mock_snowflake, mock_redis):
        """Test updating a score that has JSON contributing_sources string."""
        score_id = str(uuid4())
        company_id = str(uuid4())
        now = datetime.now(timezone.utc)

        original_row = _make_score_row(company_id=company_id)
        updated_row = dict(original_row)
        updated_row["contributing_sources"] = '["sec_filing", "glassdoor"]'

        mock_snowflake.execute_one.side_effect = [original_row, updated_row]
        mock_snowflake.execute_write.return_value = 1

        with patch("app.routers.scores.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.scores.get_redis_cache", return_value=mock_redis):
                response = client.put(
                    f"/api/v1/scores/{score_id}",
                    json={"score": 75.0}
                )

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/v1/scores/companies/{company_id}/dimension-scores
# ---------------------------------------------------------------------------

class TestGetDimensionScores:
    """Tests for GET /api/v1/scores/companies/{company_id}/dimension-scores."""

    def test_get_scores_company_not_found(self, client, mock_snowflake):
        """Test returns 404 when company doesn't exist."""
        mock_snowflake.execute_one.return_value = None

        with patch("app.routers.scores.get_snowflake_service", return_value=mock_snowflake):
            response = client.get(f"/api/v1/scores/companies/{uuid4()}/dimension-scores")

        assert response.status_code == 404

    def test_get_scores_company_found_empty(self, client, mock_snowflake):
        """Test returns empty list when company exists but has no scores."""
        company_id = str(uuid4())
        mock_snowflake.execute_one.return_value = {"id": company_id}
        mock_snowflake.execute_query.return_value = []

        with patch("app.routers.scores.get_snowflake_service", return_value=mock_snowflake):
            response = client.get(f"/api/v1/scores/companies/{company_id}/dimension-scores")

        assert response.status_code == 200
        assert response.json() == []

    def test_get_scores_company_found_with_data(self, client, mock_snowflake):
        """Test returns dimension scores when company has scores."""
        company_id = str(uuid4())
        mock_snowflake.execute_one.return_value = {"id": company_id}
        mock_snowflake.execute_query.return_value = [
            _make_score_row(company_id=company_id, dimension="data_infrastructure"),
            _make_score_row(company_id=company_id, dimension="ai_governance"),
        ]

        with patch("app.routers.scores.get_snowflake_service", return_value=mock_snowflake):
            response = client.get(f"/api/v1/scores/companies/{company_id}/dimension-scores")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_scores_with_json_string_sources(self, client, mock_snowflake):
        """Test that JSON string contributing_sources is parsed."""
        company_id = str(uuid4())
        row = _make_score_row(company_id=company_id)
        row["contributing_sources"] = '["sec_filing"]'

        mock_snowflake.execute_one.return_value = {"id": company_id}
        mock_snowflake.execute_query.return_value = [row]

        with patch("app.routers.scores.get_snowflake_service", return_value=mock_snowflake):
            response = client.get(f"/api/v1/scores/companies/{company_id}/dimension-scores")

        assert response.status_code == 200
        data = response.json()
        assert data[0]["contributing_sources"] == ["sec_filing"]


# ---------------------------------------------------------------------------
# POST /api/v1/scores/companies/{company_id}/compute-dimension-scores
# ---------------------------------------------------------------------------

class TestComputeDimensionScores:
    """Tests for POST compute-dimension-scores."""

    def test_compute_dimension_scores_company_not_found(self, client, mock_snowflake, mock_redis):
        """Test returns 404 when company doesn't exist."""
        mock_snowflake.execute_one.return_value = None

        with patch("app.routers.scores.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.scores.get_redis_cache", return_value=mock_redis):
                response = client.post(
                    f"/api/v1/scores/companies/{uuid4()}/compute-dimension-scores"
                )

        assert response.status_code == 404

    def test_compute_dimension_scores_success(self, client, mock_snowflake, mock_redis):
        """Test compute dimension scores runs pipeline and returns scores."""
        company_id = str(uuid4())
        mock_snowflake.execute_one.return_value = {"id": company_id}
        mock_snowflake.execute_query.return_value = [
            _make_score_row(company_id=company_id, dimension="data_infrastructure"),
        ]

        mock_pipeline = MagicMock()
        mock_pipeline.compute_and_store.return_value = None

        with patch("app.routers.scores.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.scores.get_redis_cache", return_value=mock_redis):
                with patch("app.routers.scores.DimensionScoringPipeline", return_value=mock_pipeline):
                    response = client.post(
                        f"/api/v1/scores/companies/{company_id}/compute-dimension-scores"
                    )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


# ---------------------------------------------------------------------------
# GET /api/v1/scores/companies/{company_id}/org-air
# ---------------------------------------------------------------------------

def _make_org_air_scores(company_id: str = None) -> "OrgAIRScores":
    """Build a minimal OrgAIRScores dataclass instance."""
    from app.pipelines.org_air_pipeline import OrgAIRScores
    cid = company_id or str(uuid4())
    return OrgAIRScores(
        company_id=cid,
        ticker="TEST",
        company_name="Test Company",
        sector="technology",
        vr_score=70.0,
        hr_score=65.0,
        synergy_score=0.8,
        org_air_score=72.0,
        confidence_lower=67.0,
        confidence_upper=77.0,
        talent_concentration=0.6,
        position_factor=0.7,
        evidence_count=10,
        dimension_scores={"data_infrastructure": 70.0},
    )


class TestGetOrgAir:
    """Tests for GET /api/v1/scores/companies/{company_id}/org-air."""

    def test_get_org_air_success(self, client, mock_snowflake):
        """Test getting org-air scores when company exists."""
        company_id = str(uuid4())
        scores = _make_org_air_scores(company_id)

        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = scores

        with patch("app.routers.scores.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.scores.OrgAIRPipeline", return_value=mock_pipeline):
                response = client.get(f"/api/v1/scores/companies/{company_id}/org-air")

        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "TEST"
        assert data["org_air_score"] == 72.0

    def test_get_org_air_company_not_found(self, client, mock_snowflake):
        """Test 404 when OrgAIRPipeline raises ValueError."""
        mock_pipeline = MagicMock()
        mock_pipeline.run.side_effect = ValueError("Company not found")

        with patch("app.routers.scores.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.scores.OrgAIRPipeline", return_value=mock_pipeline):
                response = client.get(f"/api/v1/scores/companies/{uuid4()}/org-air")

        assert response.status_code == 404


class TestListOrgAir:
    """Tests for GET /api/v1/scores/org-air."""

    def test_list_org_air_empty(self, client, mock_snowflake):
        """Test listing org-air when no companies exist."""
        mock_snowflake.execute_query.return_value = []

        with patch("app.routers.scores.get_snowflake_service", return_value=mock_snowflake):
            response = client.get("/api/v1/scores/org-air")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_org_air_skips_failures(self, client, mock_snowflake):
        """Test list_org_air skips companies that fail scoring."""
        company_id = str(uuid4())
        mock_snowflake.execute_query.return_value = [
            {"id": company_id, "name": "Test Co", "ticker": "TEST"}
        ]

        mock_pipeline = MagicMock()
        mock_pipeline.run.side_effect = Exception("missing data")

        with patch("app.routers.scores.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.scores.OrgAIRPipeline", return_value=mock_pipeline):
                response = client.get("/api/v1/scores/org-air")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_org_air_with_ticker_filter(self, client, mock_snowflake):
        """Test listing org-air filtered by ticker."""
        company_id = str(uuid4())
        mock_snowflake.execute_query.return_value = [
            {"id": company_id, "name": "Apple Inc.", "ticker": "AAPL"},
            {"id": str(uuid4()), "name": "Microsoft Corp.", "ticker": "MSFT"},
        ]
        scores = _make_org_air_scores(company_id)
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = scores

        with patch("app.routers.scores.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.scores.OrgAIRPipeline", return_value=mock_pipeline):
                response = client.get("/api/v1/scores/org-air?ticker=AAPL")

        assert response.status_code == 200
        # Only AAPL would be in wanted set, MSFT would be filtered out
        # But pipeline.run would be called for AAPL - mock returns TEST ticker
        data = response.json()
        assert isinstance(data, list)


class TestComputeOrgAir:
    """Tests for POST /api/v1/scores/companies/{company_id}/compute-org-air."""

    def test_compute_org_air_success(self, client, mock_snowflake, mock_redis):
        """Test compute org-air runs both pipelines and persists."""
        company_id = str(uuid4())
        scores = _make_org_air_scores(company_id)

        mock_dim_pipeline = MagicMock()
        mock_dim_pipeline.compute_and_store.return_value = None

        mock_org_pipeline = MagicMock()
        mock_org_pipeline.run.return_value = scores

        with patch("app.routers.scores.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.scores.get_redis_cache", return_value=mock_redis):
                with patch("app.routers.scores.DimensionScoringPipeline", return_value=mock_dim_pipeline):
                    with patch("app.routers.scores.OrgAIRPipeline", return_value=mock_org_pipeline):
                        response = client.post(
                            f"/api/v1/scores/companies/{company_id}/compute-org-air"
                        )

        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "TEST"

    def test_compute_org_air_dimension_pipeline_fails(self, client, mock_snowflake, mock_redis):
        """Test 500 when dimension scoring pipeline raises."""
        mock_dim_pipeline = MagicMock()
        mock_dim_pipeline.compute_and_store.side_effect = RuntimeError("DB error")

        with patch("app.routers.scores.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.scores.get_redis_cache", return_value=mock_redis):
                with patch("app.routers.scores.DimensionScoringPipeline", return_value=mock_dim_pipeline):
                    response = client.post(
                        f"/api/v1/scores/companies/{uuid4()}/compute-org-air"
                    )

        assert response.status_code == 500

    def test_compute_org_air_pipeline_not_found(self, client, mock_snowflake, mock_redis):
        """Test 404 when OrgAIRPipeline raises ValueError."""
        mock_dim_pipeline = MagicMock()
        mock_dim_pipeline.compute_and_store.return_value = None

        mock_org_pipeline = MagicMock()
        mock_org_pipeline.run.side_effect = ValueError("Company not found")

        with patch("app.routers.scores.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.scores.get_redis_cache", return_value=mock_redis):
                with patch("app.routers.scores.DimensionScoringPipeline", return_value=mock_dim_pipeline):
                    with patch("app.routers.scores.OrgAIRPipeline", return_value=mock_org_pipeline):
                        response = client.post(
                            f"/api/v1/scores/companies/{uuid4()}/compute-org-air"
                        )

        assert response.status_code == 404


class TestComputeAll:
    """Tests for POST /api/v1/scores/companies/{company_id}/score-company."""

    def test_compute_all_company_not_found(self, client, mock_snowflake, mock_redis):
        """Test 404 when company doesn't exist."""
        mock_snowflake.execute_one.return_value = None

        with patch("app.routers.scores.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.scores.get_redis_cache", return_value=mock_redis):
                response = client.post(
                    f"/api/v1/scores/companies/{uuid4()}/score-company"
                )

        assert response.status_code == 404

    def test_compute_all_success(self, client, mock_snowflake, mock_redis):
        """Test compute all scores runs both pipelines."""
        company_id = str(uuid4())
        mock_snowflake.execute_one.return_value = {"id": company_id}
        mock_snowflake.execute_query.return_value = [
            _make_score_row(company_id=company_id, dimension="data_infrastructure"),
        ]

        scores = _make_org_air_scores(company_id)
        mock_dim_pipeline = MagicMock()
        mock_dim_pipeline.compute_and_store.return_value = None
        mock_org_pipeline = MagicMock()
        mock_org_pipeline.run.return_value = scores

        with patch("app.routers.scores.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.scores.get_redis_cache", return_value=mock_redis):
                with patch("app.routers.scores.DimensionScoringPipeline", return_value=mock_dim_pipeline):
                    with patch("app.routers.scores.OrgAIRPipeline", return_value=mock_org_pipeline):
                        response = client.post(
                            f"/api/v1/scores/companies/{company_id}/score-company"
                        )

        assert response.status_code == 200
        data = response.json()
        assert "dimension_scores" in data
        assert "org_air" in data

    def test_compute_all_dim_pipeline_fails(self, client, mock_snowflake, mock_redis):
        """Test 500 when dimension scoring fails in compute_all."""
        company_id = str(uuid4())
        mock_snowflake.execute_one.return_value = {"id": company_id}

        mock_dim_pipeline = MagicMock()
        mock_dim_pipeline.compute_and_store.side_effect = RuntimeError("error")

        with patch("app.routers.scores.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.scores.get_redis_cache", return_value=mock_redis):
                with patch("app.routers.scores.DimensionScoringPipeline", return_value=mock_dim_pipeline):
                    response = client.post(
                        f"/api/v1/scores/companies/{company_id}/score-company"
                    )

        assert response.status_code == 500

    def test_compute_all_org_pipeline_not_found(self, client, mock_snowflake, mock_redis):
        """Test 404 when OrgAIR pipeline can't find company in compute_all."""
        company_id = str(uuid4())
        mock_snowflake.execute_one.return_value = {"id": company_id}
        mock_snowflake.execute_query.return_value = []

        mock_dim_pipeline = MagicMock()
        mock_dim_pipeline.compute_and_store.return_value = None
        mock_org_pipeline = MagicMock()
        mock_org_pipeline.run.side_effect = ValueError("not found")

        with patch("app.routers.scores.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.scores.get_redis_cache", return_value=mock_redis):
                with patch("app.routers.scores.DimensionScoringPipeline", return_value=mock_dim_pipeline):
                    with patch("app.routers.scores.OrgAIRPipeline", return_value=mock_org_pipeline):
                        response = client.post(
                            f"/api/v1/scores/companies/{company_id}/score-company"
                        )

        assert response.status_code == 404


class TestScoreByTicker:
    """Tests for POST /api/v1/scores/score-by-ticker."""

    def test_score_by_ticker_success(self, client, mock_snowflake):
        """Test score-by-ticker returns result from integration service."""
        from app.pipelines.org_air_pipeline import OrgAIRScores
        mock_service = MagicMock()
        mock_service.score_company.return_value = {"ticker": "TEST", "score": 72.0}

        with patch("app.routers.scores.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.scores.ScoringIntegrationService", return_value=mock_service):
                response = client.post(
                    "/api/v1/scores/score-by-ticker",
                    json={"ticker": "TEST"}
                )

        assert response.status_code == 200

    def test_score_by_ticker_not_found(self, client, mock_snowflake):
        """Test score-by-ticker returns 404 on LookupError."""
        mock_service = MagicMock()
        mock_service.score_company.side_effect = LookupError("Company not found")

        with patch("app.routers.scores.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.scores.ScoringIntegrationService", return_value=mock_service):
                response = client.post(
                    "/api/v1/scores/score-by-ticker",
                    json={"ticker": "ZZZZ"}
                )

        assert response.status_code == 404

    def test_score_by_ticker_server_error(self, client, mock_snowflake):
        """Test score-by-ticker returns 500 on generic exception."""
        mock_service = MagicMock()
        mock_service.score_company.side_effect = RuntimeError("DB error")

        with patch("app.routers.scores.get_snowflake_service", return_value=mock_snowflake):
            with patch("app.routers.scores.ScoringIntegrationService", return_value=mock_service):
                response = client.post(
                    "/api/v1/scores/score-by-ticker",
                    json={"ticker": "TEST"}
                )

        assert response.status_code == 500
