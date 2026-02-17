from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
from decimal import Decimal


class Dimension(str, Enum):
    DATA_INFRASTRUCTURE = "data_infrastructure"
    AI_GOVERNANCE = "ai_governance"
    TECHNOLOGY_STACK = "technology_stack"
    TALENT = "talent"
    LEADERSHIP = "leadership"
    USE_CASE_PORTFOLIO = "use_case_portfolio"
    CULTURE = "culture"


class SignalSource(str, Enum):
    # CS2 External Signals
    TECHNOLOGY_HIRING = "technology_hiring"
    INNOVATION_ACTIVITY = "innovation_activity"
    DIGITAL_PRESENCE = "digital_presence"
    LEADERSHIP_SIGNALS = "leadership_signals"
    # CS2 SEC Sections
    SEC_ITEM_1 = "sec_item_1"
    SEC_ITEM_1A = "sec_item_1a"
    SEC_ITEM_7 = "sec_item_7"
    # CS3 New Sources
    GLASSDOOR_REVIEWS = "glassdoor_reviews"
    BOARD_COMPOSITION = "board_composition"


@dataclass
class DimensionMapping:
    """Maps a signal source to dimensions with weights."""

    source: SignalSource
    primary_dimension: Dimension
    primary_weight: Decimal
    secondary_mappings: Dict[Dimension, Decimal] = field(default_factory=dict)
    reliability: Decimal = Decimal("0.8")  # Source reliability


@dataclass
class EvidenceScore:
    """A score from a single evidence source."""

    source: SignalSource
    raw_score: Decimal  # 0-100
    confidence: Decimal  # 0-1
    evidence_count: int
    metadata: Dict = field(default_factory=dict)


@dataclass
class DimensionScore:
    """Aggregated score for one dimension."""

    dimension: Dimension
    score: Decimal
    contributing_sources: List[SignalSource]
    total_weight: Decimal


# Mapper table define weights and reliabilities for each source-dimension mapping
SIGNAL_TO_DIMENSION_MAP: Dict[SignalSource, DimensionMapping] = {
    SignalSource.TECHNOLOGY_HIRING: DimensionMapping(
        source=SignalSource.TECHNOLOGY_HIRING,
        primary_dimension=Dimension.TECHNOLOGY_STACK,
        primary_weight=Decimal("0.7"),
        secondary_mappings={
            Dimension.TALENT: Decimal("0.2"),
            Dimension.INNOVATION_ACTIVITY: Decimal("0.1"),
        },
        reliability=Decimal("0.9"),
    ),
    SignalSource.INNOVATION_ACTIVITY: DimensionMapping(
        source=SignalSource.INNOVATION_ACTIVITY,
        primary_dimension=Dimension.INNOVATION_ACTIVITY,
        primary_weight=Decimal("0.8"),
        secondary_mappings={
            Dimension.TECHNOLOGY_STACK: Decimal("0.1"),
            Dimension.CULTURE: Decimal("0.1"),
        },
        reliability=Decimal("0.85"),
    ),
    SignalSource.DIGITAL_PRESENCE: DimensionMapping(
        source=SignalSource.DIGITAL_PRESENCE,
        primary_dimension=Dimension.TECHNOLOGY_STACK,
        primary_weight=Decimal("0.6"),
        secondary_mappings={
            Dimension.DATA_INFRASTRUCTURE: Decimal("0.4"),
        },
        reliability=Decimal("0.75"),
    ),
    SignalSource.LEADERSHIP_SIGNALS: DimensionMapping(
        source=SignalSource.LEADERSHIP_SIGNALS,
        primary_dimension=Dimension.LEADERSHIP,
        primary_weight=Decimal("0.7"),
        secondary_mappings={
            Dimension.CULTURE: Decimal("0.1"),
            Dimension.AI_GOVERNANCE: Decimal("0.2"),
        },
        reliability=Decimal("0.95"),
    ),
    SignalSource.SEC_ITEM_1: DimensionMapping(
        source=SignalSource.SEC_ITEM_1,
        primary_dimension=Dimension.USE_CASE_PORTFOLIO,
        primary_weight=Decimal("0.5"),
        secondary_mappings={
            Dimension.TECHNOLOGY_STACK: Decimal("0.2"),
            Dimension.LEADERSHIP: Decimal("0.3"),
        },
        reliability=Decimal("0.95"),
    ),
    SignalSource.SEC_ITEM_1A: DimensionMapping(
        source=SignalSource.SEC_ITEM_1A,
        primary_dimension=Dimension.AI_GOVERNANCE,
        primary_weight=Decimal("0.6"),
        secondary_mappings={Dimension.DATA_INFRASTRUCTURE: Decimal("0.4")},
        reliability=Decimal("0.9"),
    ),
    SignalSource.SEC_ITEM_7: DimensionMapping(
        source=SignalSource.SEC_ITEM_7,
        primary_dimension=Dimension.LEADERSHIP,
        primary_weight=Decimal("0.6"),
        secondary_mappings={
            Dimension.USE_CASE_PORTFOLIO: Decimal("0.2"),
            Dimension.DATA_INFRASTRUCTURE: Decimal("0.2"),
        },
        reliability=Decimal("0.9"),
    ),
    SignalSource.GLASSDOOR_REVIEWS: DimensionMapping(
        source=SignalSource.GLASSDOOR_REVIEWS,
        primary_dimension=Dimension.CULTURE,
        primary_weight=Decimal("0.7"),
        secondary_mappings={
            Dimension.TALENT: Decimal("0.2"),
            Dimension.LEADERSHIP: Decimal("0.1"),
        },
        reliability=Decimal("0.6"),
    ),
    SignalSource.BOARD_COMPOSITION: DimensionMapping(
        source=SignalSource.BOARD_COMPOSITION,
        primary_dimension=Dimension.LEADERSHIP,
        primary_weight=Decimal("0.7"),
        secondary_mappings={Dimension.LEADERSHIP: Decimal("0.3")},
        reliability=Decimal("0.85"),
    ),
}
