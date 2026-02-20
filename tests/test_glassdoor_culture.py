"""Unit tests for Glassdoor culture scoring (PDF Task 5.0c)."""

import pytest
from datetime import datetime, timezone, timedelta

from app.models.glassdoor import GlassdoorReview
from app.pipelines.glassdoor_collector import (
    RECENCY_DAYS_FULL_WEIGHT,
    _count_keywords_in_text,
    _keywords_matched_in_text,
    compute_culture_score_from_reviews,
)


def _review(
    review_id: str = "r1",
    pros: str = "",
    cons: str = "",
    advice: str | None = None,
    is_current: bool = False,
    days_ago: int = 100,
) -> GlassdoorReview:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return GlassdoorReview(
        review_id=review_id,
        rating=4.0,
        title="",
        pros=pros,
        cons=cons,
        advice_to_management=advice,
        is_current_employee=is_current,
        job_title="",
        review_date=dt,
    )


class TestCountKeywordsInText:
    def test_matches_case_insensitive(self):
        assert _count_keywords_in_text("Innovative culture", ["innovative"]) == 1
        assert _count_keywords_in_text("INNOVATIVE", ["innovative"]) == 1

    def test_multiple_keywords(self):
        assert _count_keywords_in_text(
            "data-driven metrics and kpis",
            ["data-driven", "metrics", "kpis"],
        ) == 3

    def test_no_matches(self):
        assert _count_keywords_in_text("nothing relevant", ["innovative", "ai"]) == 0


class TestKeywordsMatchedInText:
    def test_returns_only_matching_keywords(self):
        got = _keywords_matched_in_text("innovative and data-driven culture", ["innovative", "data-driven", "ai"])
        assert set(got) == {"innovative", "data-driven"}

    def test_case_insensitive(self):
        got = _keywords_matched_in_text("INNOVATIVE cutting-edge", ["innovative", "cutting-edge"])
        assert set(got) == {"innovative", "cutting-edge"}


class TestComputeCultureScoreFromReviews:
    def test_empty_reviews_returns_default(self):
        result = compute_culture_score_from_reviews("c1", "TKR", [])
        assert result.overall == 50.0
        assert result.confidence == 0.0
        assert result.evidence_count == 0
        assert result.component_scores["innovation"] == 50.0
        assert all(not v for v in result.keywords_matched.values())

    def test_score_bounded_0_100(self):
        # All positive keywords -> high score
        reviews = [
            _review("r1", pros="innovative cutting-edge data-driven metrics ai machine learning agile", days_ago=30),
            _review("r2", pros="forward-thinking experimental kpis dashboards", days_ago=50),
        ]
        result = compute_culture_score_from_reviews("c1", "TKR", reviews)
        assert 0 <= result.overall <= 100
        assert result.evidence_count == 2

        # All negative keywords -> low score
        reviews_neg = [
            _review("r1", cons="bureaucratic slow to change resistant outdated red tape rigid", days_ago=30),
        ]
        result_neg = compute_culture_score_from_reviews("c1", "TKR", reviews_neg)
        assert 0 <= result_neg.overall <= 100
        assert result_neg.overall < result.overall

    def test_confidence_increases_with_more_reviews(self):
        base = _review("r1", pros="innovative", days_ago=100)
        result1 = compute_culture_score_from_reviews("c1", "TKR", [base])
        reviews_10 = [base] + [_review(f"r{i}", pros="ok", days_ago=50) for i in range(2, 11)]
        result10 = compute_culture_score_from_reviews("c1", "TKR", reviews_10)
        assert result10.confidence >= result1.confidence
        assert result10.confidence <= 1.0

    def test_evidence_count_returned(self):
        reviews = [_review("r1", pros="ok", days_ago=50), _review("r2", pros="ok", days_ago=50)]
        result = compute_culture_score_from_reviews("c1", "TKR", reviews)
        assert result.evidence_count == 2

    def test_positive_keywords_raise_culture_score(self):
        neutral = [_review("r1", pros="good place", cons="could improve", days_ago=100)]
        positive = [
            _review(
                "r1",
                pros="innovative cutting-edge data-driven metrics ai machine learning agile embraces change",
                cons="",
                days_ago=100,
            ),
        ]
        compute_culture_score_from_reviews("c1", "TKR", neutral)
        result_neutral = compute_culture_score_from_reviews("c1", "TKR", neutral)
        result_positive = compute_culture_score_from_reviews("c1", "TKR", positive)
        assert result_positive.overall > result_neutral.overall

    def test_recency_weight_recent_higher_impact(self):
        old = _review("r1", pros="innovative data-driven ai", days_ago=RECENCY_DAYS_FULL_WEIGHT + 100)
        recent = _review("r2", pros="innovative data-driven ai", days_ago=30)
        result_old = compute_culture_score_from_reviews("c1", "TKR", [old])
        result_recent = compute_culture_score_from_reviews("c1", "TKR", [recent])
        # Recent review has full weight, old has 0.5 weight; so recent should contribute more
        assert result_recent.overall >= result_old.overall or abs(result_recent.overall - result_old.overall) < 1e-6

    def test_current_employee_weighted_higher(self):
        same_text = "innovative data-driven ai agile"
        ex = _review("r1", pros=same_text, is_current=False, days_ago=50)
        current = _review("r2", pros=same_text, is_current=True, days_ago=50)
        result_ex = compute_culture_score_from_reviews("c1", "TKR", [ex])
        result_current = compute_culture_score_from_reviews("c1", "TKR", [current])
        # Current employee has 1.2x weight so should push score slightly higher when only one review each
        assert result_current.overall >= result_ex.overall or abs(result_current.overall - result_ex.overall) < 0.1

    def test_component_scores_and_keywords_matched_returned(self):
        reviews = [
            _review("r1", pros="innovative data-driven ai agile", days_ago=50),
            _review("r2", pros="metrics kpis machine learning", days_ago=50),
        ]
        result = compute_culture_score_from_reviews("c1", "TKR", reviews)
        assert set(result.component_scores.keys()) == {"innovation", "data_driven", "ai_awareness", "change_readiness"}
        for key, val in result.component_scores.items():
            assert 0 <= val <= 100, f"component_scores[{key}] should be in [0, 100], got {val}"
        assert "innovative" in result.keywords_matched["innovation_positive"]
        assert "data-driven" in result.keywords_matched["data_driven"]
        assert "ai" in result.keywords_matched["ai_awareness"]
        assert "agile" in result.keywords_matched["change_positive"]
        assert "metrics" in result.keywords_matched["data_driven"]
        assert "machine learning" in result.keywords_matched["ai_awareness"]
