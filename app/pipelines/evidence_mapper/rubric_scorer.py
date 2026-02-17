from app.pipelines.evidence_mapper.score_rubric import DIMENSION_RUBRICS, RubricResult


class RubricScorer:
    def __init__(self, rubric):
        self.rubric = DIMENSION_RUBRICS

    def score_dimension(
        self,
        dimension: str,
        evidence_text: str,
        quantitative_metrics: Dict[str, float],
    ) -> RubricResult:
        """Scores a dimension based on evidence using the rubric."""
