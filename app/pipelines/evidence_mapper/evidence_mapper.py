from decimal import Decimal
from typing import Dict, List, Optional

from app.models.enums import Dimension
from app.pipelines.evidence_mapper.evidence_mapping_table import (
    SIGNAL_TO_DIMENSION_MAP,
    EvidenceScore,
    DimensionScore,
    DimensionMapping,
    SignalSource,
)


class EvidenceMapper:

    def __init__(self, signal_map: Optional[Dict[SignalSource, DimensionMapping]] = None):
        self.evidence_mapper = signal_map if signal_map is not None else SIGNAL_TO_DIMENSION_MAP

    def map_evidence_to_dimensions(
        self, evidence_scores: List[EvidenceScore]
    ) -> Dict[Dimension, DimensionScore]:

        weighted_sums: Dict[Dimension, Decimal] = {d: Decimal("0") for d in Dimension}
        weight_totals: Dict[Dimension, Decimal] = {d: Decimal("0") for d in Dimension}
        source_lists: Dict[Dimension, list] = {d: [] for d in Dimension}

        for ev in evidence_scores:
            # Look up the mapping for this evidence source
            mapping = self.evidence_mapper.get(ev.source)
            if mapping is None:
                continue

            # Create list of Tuple (dimension_type, weight) pairs including primary and secondary mappings
            pairs = [(mapping.primary_dimension, mapping.primary_weight)] + list(
                mapping.secondary_mappings.items()
            )

            for dim, weight in pairs:

                # Calculate effective weight considering evidence confidence from external signal and source reliability defined in the mapping table
                effective_weight = weight * ev.confidence * mapping.reliability
                # Accumulate weighted scores and total weights for each dimension
                weighted_sums[dim] += ev.raw_score * effective_weight
                weight_totals[dim] += effective_weight
                if ev.source not in source_lists[dim]:
                    source_lists[dim].append(ev.source)

        result: Dict[Dimension, DimensionScore] = {}

        for d in Dimension:
            if weight_totals[d] > 0:

                # Calculate final score as weighted average of evidence scores for this dimension
                raw = weighted_sums[d] / weight_totals[d]
                # Normalized to 0-100
                score = max(Decimal("0"), min(Decimal("100"), raw))
                confidence = min(Decimal("1.0"), weight_totals[d] / Decimal("2"))
            else:
                # If no evidence, assign a default score (e.g., 50) and zero confidence
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
