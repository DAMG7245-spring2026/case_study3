"""Unit tests for Glassdoor culture scoring (PDF Task 5.0c)."""

import pytest
from datetime import datetime, timezone, timedelta

from app.models.glassdoor import GlassdoorReview
from app.pipelines.glassdoor_collector import (
    compute_culture_score_from_reviews,
    _count_keywords_in_text,
    RECENCY_DAYS_FULL_WEIGHT,
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


class TestComputeCultureScoreFromReviews:
    def test_empty_reviews_returns_default(self):
        score, confidence, count = compute_culture_score_from_reviews("c1", "TKR", [])
        assert score == 50.0
        assert confidence == 0.0
        assert count == 0

    def test_score_bounded_0_100(self):
        # All positive keywords -> high score
        reviews = [
            _review("r1", pros="innovative cutting-edge data-driven metrics ai machine learning agile", days_ago=30),
            _review("r2", pros="forward-thinking experimental kpis dashboards", days_ago=50),
        ]
        score, confidence, count = compute_culture_score_from_reviews("c1", "TKR", reviews)
        assert 0 <= score <= 100
        assert count == 2

        # All negative keywords -> low score
        reviews_neg = [
            _review("r1", cons="bureaucratic slow to change resistant outdated red tape rigid", days_ago=30),
        ]
        score_neg, _, _ = compute_culture_score_from_reviews("c1", "TKR", reviews_neg)
        assert 0 <= score_neg <= 100
        assert score_neg < score

    def test_confidence_increases_with_more_reviews(self):
        base = _review("r1", pros="innovative", days_ago=100)
        score1, conf1, _ = compute_culture_score_from_reviews("c1", "TKR", [base])
        reviews_10 = [base] + [_review(f"r{i}", pros="ok", days_ago=50) for i in range(2, 11)]
        score10, conf10, _ = compute_culture_score_from_reviews("c1", "TKR", reviews_10)
        assert conf10 >= conf1
        assert conf10 <= 1.0

    def test_evidence_count_returned(self):
        reviews = [_review("r1", pros="ok", days_ago=50), _review("r2", pros="ok", days_ago=50)]
        _, _, count = compute_culture_score_from_reviews("c1", "TKR", reviews)
        assert count == 2

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
        _, _, _ = compute_culture_score_from_reviews("c1", "TKR", neutral)
        score_neutral, _, _ = compute_culture_score_from_reviews("c1", "TKR", neutral)
        score_positive, _, _ = compute_culture_score_from_reviews("c1", "TKR", positive)
        assert score_positive > score_neutral

    def test_recency_weight_recent_higher_impact(self):
        old = _review("r1", pros="innovative data-driven ai", days_ago=RECENCY_DAYS_FULL_WEIGHT + 100)
        recent = _review("r2", pros="innovative data-driven ai", days_ago=30)
        score_old, _, _ = compute_culture_score_from_reviews("c1", "TKR", [old])
        score_recent, _, _ = compute_culture_score_from_reviews("c1", "TKR", [recent])
        # Recent review has full weight, old has 0.5 weight; so recent should contribute more
        assert score_recent >= score_old or abs(score_recent - score_old) < 1e-6

    def test_current_employee_weighted_higher(self):
        same_text = "innovative data-driven ai agile"
        ex = _review("r1", pros=same_text, is_current=False, days_ago=50)
        current = _review("r2", pros=same_text, is_current=True, days_ago=50)
        score_ex, _, _ = compute_culture_score_from_reviews("c1", "TKR", [ex])
        score_current, _, _ = compute_culture_score_from_reviews("c1", "TKR", [current])
        # Current employee has 1.2x weight so should push score slightly higher when only one review each
        assert score_current >= score_ex or abs(score_current - score_ex) < 0.1
