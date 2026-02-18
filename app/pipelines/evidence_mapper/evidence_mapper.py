from decimal import Decimal
from typing import Dict, List

from app.models.enums import Dimension
from app.pipelines.evidence_mapper.evidence_mapping_table import (
    SIGNAL_TO_DIMENSION_MAP,
    EvidenceScore,
    DimensionScore,
    DimensionMapping,
)


class EvidenceMapper:

    def __init__(self):
        self.evidence_mapper = SIGNAL_TO_DIMENSION_MAP

    def map_evidence_to_dimensions(
        self, evidence_scores: List[EvidenceScore]
    ) -> Dict[Dimension, DimensionScore]:
        weighted_sums: Dict[Dimension, Decimal] = {d: Decimal("0") for d in Dimension}
        weight_totals: Dict[Dimension, Decimal] = {d: Decimal("0") for d in Dimension}
        source_lists: Dict[Dimension, list] = {d: [] for d in Dimension}

        for ev in evidence_scores:
            mapping = self.evidence_mapper.get(ev.source)
            if mapping is None:
                continue
            pairs = [(mapping.primary_dimension, mapping.primary_weight)] + list(
                mapping.secondary_mappings.items()
            )
            for dim, weight in pairs:
                effective_weight = weight * ev.confidence * mapping.reliability
                weighted_sums[dim] += ev.raw_score * effective_weight
                weight_totals[dim] += effective_weight
                if ev.source not in source_lists[dim]:
                    source_lists[dim].append(ev.source)

        result: Dict[Dimension, DimensionScore] = {}
        for d in Dimension:
            if weight_totals[d] > 0:
                raw = weighted_sums[d] / weight_totals[d]
                score = max(Decimal("0"), min(Decimal("100"), raw))
                confidence = min(Decimal("1.0"), weight_totals[d] / Decimal("2"))
            else:
                score = Decimal("50")
                confidence = Decimal("0")
            result[d] = DimensionScore(
                dimension=d,
                score=score,
                contributing_sources=source_lists[d],
                total_weight=weight_totals[d],
                confidence=confidence,
            )
        return result

    def get_coverage_report(
        self, evidence_scores: List[EvidenceScore]
    ) -> Dict[Dimension, Dict]:
        weight_totals: Dict[Dimension, Decimal] = {d: Decimal("0") for d in Dimension}
        source_lists: Dict[Dimension, list] = {d: [] for d in Dimension}

        for ev in evidence_scores:
            mapping = self.evidence_mapper.get(ev.source)
            if mapping is None:
                continue
            pairs = [(mapping.primary_dimension, mapping.primary_weight)] + list(
                mapping.secondary_mappings.items()
            )
            for dim, weight in pairs:
                effective_weight = weight * ev.confidence * mapping.reliability
                weight_totals[dim] += effective_weight
                if ev.source not in source_lists[dim]:
                    source_lists[dim].append(ev.source)

        return {
            d: {
                "has_evidence": weight_totals[d] > 0,
                "source_count": len(source_lists[d]),
                "total_weight": float(weight_totals[d]),
                "confidence": float(
                    min(Decimal("1.0"), weight_totals[d] / Decimal("2"))
                    if weight_totals[d] > 0
                    else Decimal("0")
                ),
            }
            for d in Dimension
        }
