from typing import Dict, List
from decimal import Decimal

from app.pipelines.evidence_mapper.score_rubric import (
    DIMENSION_RUBRICS,
    RubricResult,
    ScoreLevel,
    RubricCriteria,
)


class RubricScorer:

    def __init__(self):
        self.rubrics = DIMENSION_RUBRICS

    def score_dimension(
        self,
        dimension: str,
        evidence_text: str,
        quantitative_metrics: Dict[str, float],
    ) -> RubricResult:
        """Scores a dimension based on evidence using the rubric."""
        text = evidence_text.lower()
        rubric_levels = self.rubrics.get(dimension, [])

        for criteria in rubric_levels:
            matches = [kw for kw in criteria.keywords if kw.lower() in text]
            quant_value = (
                max(quantitative_metrics.values(), default=0.0)
                if quantitative_metrics
                else 0.0
            )
            keyword_ok = len(matches) >= criteria.min_keyword_matches
            quant_ok = (
                quant_value >= criteria.quantitative_threshold
                or criteria.quantitative_threshold == 0.0
            )

            if keyword_ok and quant_ok:
                extra = len(matches) - criteria.min_keyword_matches
                max_extra = max(
                    1, len(criteria.keywords) - criteria.min_keyword_matches
                )
                ratio = min(1.0, extra / max_extra)
                score = criteria.level.min_score + ratio * (
                    criteria.level.max_score - criteria.level.min_score
                )
                confidence = min(
                    Decimal("1.0"),
                    Decimal(str(len(matches)))
                    / Decimal(str(max(1, criteria.min_keyword_matches))),
                )
                rationale = (
                    f"Level {criteria.level.value[2]}: matched {len(matches)} keywords"
                )
                return RubricResult(
                    dimension=dimension,
                    level=criteria.level,
                    score=Decimal(str(round(score, 2))),
                    matched_keywords=matches,
                    keyword_match_count=len(matches),
                    confidence=confidence,
                    rationale=rationale,
                )

        # Fallback: LEVEL_1, no matches
        return RubricResult(
            dimension=dimension,
            level=ScoreLevel.LEVEL_1,
            score=Decimal("10"),
            matched_keywords=[],
            keyword_match_count=0,
            confidence=Decimal("0.3"),
            rationale="Level Nascent: no keyword matches",
        )

    def score_all_dimensions(
        self,
        evidence_by_dimension: Dict[str, str],
        metrics_by_dimension: Dict[str, Dict[str, float]],
    ) -> Dict[str, RubricResult]:
        return {
            dim: self.score_dimension(
                dim,
                evidence_by_dimension.get(dim, ""),
                metrics_by_dimension.get(dim, {}),
            )
            for dim in self.rubrics.keys()
        }
