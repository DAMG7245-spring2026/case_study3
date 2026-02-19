"""Dimension scoring pipeline.

Orchestrates evidence fetching, rubric scoring, and dimension score persistence
for a single company.

Flow:
  1. Fetch aggregated external signals from Snowflake (one row per category)
  2. Fetch SEC document chunks (item_1, item_1a, item_7) from Snowflake
  3. Convert external signals → EvidenceScore objects
  4. Score each SEC section with RubricScorer → EvidenceScore objects
  5. Feed all EvidenceScores into EvidenceMapper.map_evidence_to_dimensions()
  6. Upsert all 7 dimension scores to Snowflake
"""
import logging
from collections import defaultdict
from decimal import Decimal

from app.models.enums import DIMENSION_WEIGHTS, Dimension
from app.pipelines.evidence_mapper.evidence_mapper import EvidenceMapper
from app.pipelines.evidence_mapper.evidence_mapping_table import (
    EvidenceScore,
    SIGNAL_TO_DIMENSION_MAP,
    SignalSource,
)
from app.pipelines.evidence_mapper.rubric_scorer import RubricScorer
from app.services.snowflake import SnowflakeService

logger = logging.getLogger(__name__)

# Map external_signals.category → SignalSource enum
CATEGORY_TO_SOURCE: dict[str, SignalSource] = {
    "technology_hiring": SignalSource.TECHNOLOGY_HIRING,
    "innovation_activity": SignalSource.INNOVATION_ACTIVITY,
    "digital_presence": SignalSource.DIGITAL_PRESENCE,
    "leadership_signals": SignalSource.LEADERSHIP_SIGNALS,
    "glassdoor_reviews": SignalSource.GLASSDOOR_REVIEWS,
    "board_composition": SignalSource.BOARD_COMPOSITION,
}

# Map document_chunks.section → SignalSource enum
SECTION_TO_SOURCE: dict[str, SignalSource] = {
    "item_1": SignalSource.SEC_ITEM_1,
    "item_1a": SignalSource.SEC_ITEM_1A,
    "item_7": SignalSource.SEC_ITEM_7,
}


class DimensionScoringPipeline:
    """Compute and persist AI-readiness dimension scores for a company."""

    def __init__(self, db: SnowflakeService) -> None:
        self.db = db
        self.mapper = EvidenceMapper()
        self.rubric = RubricScorer()

    def compute_and_store(self, company_id: str) -> list[dict]:
        """Run the full scoring pipeline and upsert results to Snowflake.

        Args:
            company_id: The company UUID string.

        Returns:
            List of dicts with keys: dimension, score, confidence,
            total_weight, evidence_count, contributing_sources.
        """
        evidence_scores: list[EvidenceScore] = []

        # ── A. External signals ──────────────────────────────────────────
        signal_rows = self.db.get_signals_for_scoring(company_id)
        for row in signal_rows:
            source = CATEGORY_TO_SOURCE.get(row["category"])
            if source is None:
                logger.warning("Unknown signal category: %s", row["category"])
                continue
            if row["avg_score"] is None or row["avg_confidence"] is None:
                continue
            evidence_scores.append(
                EvidenceScore(
                    source=source,
                    raw_score=Decimal(str(row["avg_score"])),
                    confidence=Decimal(str(row["avg_confidence"])),
                    evidence_count=int(row["signal_count"]),
                )
            )
        logger.info(
            "company=%s: %d external signal categories loaded", company_id, len(signal_rows)
        )

        # ── B. SEC document chunks ───────────────────────────────────────
        chunk_rows = self.db.get_sec_chunks_for_scoring(company_id)

        # Group chunks by section, preserving order
        sections: dict[str, list[str]] = defaultdict(list)
        for row in chunk_rows:
            sections[row["section"]].append(row["content"])

        for section, contents in sections.items():
            source = SECTION_TO_SOURCE.get(section)
            if source is None:
                continue
            text = " ".join(contents)
            primary_dim: Dimension = SIGNAL_TO_DIMENSION_MAP[source].primary_dimension
            result = self.rubric.score_dimension(primary_dim.value, text, {})
            evidence_scores.append(
                EvidenceScore(
                    source=source,
                    raw_score=result.score,
                    confidence=result.confidence,
                    evidence_count=len(contents),
                )
            )
        logger.info(
            "company=%s: %d SEC sections scored", company_id, len(sections)
        )

        # ── C. Map evidence → dimensions ─────────────────────────────────
        dimension_results = self.mapper.map_evidence_to_dimensions(evidence_scores)

        # Build lookup: source → evidence_count
        source_to_count = {es.source: es.evidence_count for es in evidence_scores}

        # ── D. Upsert scores and collect return payload ──────────────────
        output = []
        for dim, dim_score in dimension_results.items():
            ev_count = sum(
                source_to_count.get(s, 0) for s in dim_score.contributing_sources
            )
            contributing = [s.value for s in dim_score.contributing_sources]
            weight = DIMENSION_WEIGHTS[dim]
            score_val = float(dim_score.score)
            conf_val = float(dim_score.confidence)

            self.db.upsert_dimension_score(
                company_id=company_id,
                dimension=dim.value,
                score=score_val,
                total_weight=weight,
                confidence=conf_val,
                evidence_count=ev_count,
                contributing_sources=contributing,
            )
            output.append(
                {
                    "dimension": dim.value,
                    "score": score_val,
                    "total_weight": weight,
                    "confidence": conf_val,
                    "evidence_count": ev_count,
                    "contributing_sources": contributing,
                }
            )

        logger.info(
            "company=%s: upserted %d dimension scores", company_id, len(output)
        )
        return output
