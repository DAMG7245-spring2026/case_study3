"""Task 5.2: V^R (Idiosyncratic Readiness) Calculator.

Full V^R formula
----------------
  V^R = D_w × (1 − λ × cv_D) × TalentRiskAdj

Where:
  D_w          = weighted_mean(7 dimension scores)
  cv_D         = coefficient_of_variation(D_w)
  λ            = 0.25  (non-compensatory penalty, PDF spec)
  penalty      = clamp(1 − λ × cv_D, 0, 1)
  TalentRiskAdj = clamp(1 − 0.15 × max(0, TC − 0.25), 0, 1)

All intermediate and final values are clamped to [0, 100].
Calculations use Decimal for financial-grade precision.
Audit trail emitted via structlog.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional

import structlog

from app.models.enums import DIMENSION_WEIGHTS, Dimension
from app.scoring.utils import (
    clamp,
    coefficient_of_variation,
    to_decimal,
    weighted_mean,
    weighted_std_dev,
)

logger = structlog.get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
LAMBDA_PENALTY: Decimal = Decimal("0.25")        # non-compensatory CV penalty
TALENT_RISK_COEFF: Decimal = Decimal("0.15")      # per-unit TC penalty above threshold
TALENT_THRESHOLD: Decimal = Decimal("0.25")       # TC threshold before penalty kicks in


@dataclass
class VRResult:
    """Full V^R calculation result with audit trail."""

    vr_score: Decimal
    weighted_mean: Decimal
    std_dev: Decimal
    coefficient_of_variation: Decimal
    penalty_factor: Decimal
    talent_concentration: Decimal
    talent_risk_adjustment: Decimal
    dimension_scores: Dict[str, Decimal]       # dimension name → clamped score
    dimension_contributions: Dict[str, Decimal]  # dimension name → weight × score

    def to_dict(self) -> dict:
        """Serialise to plain-Python dict (floats) for logging / JSON."""
        return {
            "vr_score": float(self.vr_score),
            "weighted_mean": float(self.weighted_mean),
            "std_dev": float(self.std_dev),
            "cv": float(self.coefficient_of_variation),
            "penalty_factor": float(self.penalty_factor),
            "talent_concentration": float(self.talent_concentration),
            "talent_risk_adj": float(self.talent_risk_adjustment),
            "dimension_scores": {k: float(v) for k, v in self.dimension_scores.items()},
            "dimension_contributions": {
                k: float(v) for k, v in self.dimension_contributions.items()
            },
        }


class VRCalculator:
    """Compute V^R (Idiosyncratic Readiness) score.

    Accepts dimension scores either as a ``Dict[str, float]``
    (dimension name → score 0–100) or as a ``List[float]``
    ordered by ``Dimension`` enum member order.

    Parameters
    ----------
    dimension_weights:
        Override the default ``DIMENSION_WEIGHTS`` dict from ``app.models.enums``.
        Useful for sector-specific calibration.
    lambda_penalty:
        Override λ (default 0.25).
    """

    def __init__(
        self,
        dimension_weights: Optional[Dict[Dimension, float]] = None,
        lambda_penalty: float = float(LAMBDA_PENALTY),
    ) -> None:
        self.weights: Dict[Dimension, Decimal] = {
            d: to_decimal(w)
            for d, w in (dimension_weights or DIMENSION_WEIGHTS).items()
        }
        self.lambda_penalty: Decimal = to_decimal(lambda_penalty)
        self.talent_risk_coeff: Decimal = TALENT_RISK_COEFF
        self.talent_threshold: Decimal = TALENT_THRESHOLD

        logger.info(
            "vr_calculator_initialized",
            lambda_penalty=float(self.lambda_penalty),
            weights={d.value: float(w) for d, w in self.weights.items()},
        )

    # ── public API ────────────────────────────────────────────────────────────

    def calculate(
        self,
        dimension_scores: Dict[str, float],
        talent_concentration: float,
    ) -> VRResult:
        """Calculate V^R score.

        Args:
            dimension_scores: Mapping of dimension name (str) → score (0–100).
                              Missing dimensions default to 50.0.
            talent_concentration: TC ratio in [0, 1].

        Returns:
            VRResult with full audit trail.
        """
        # ── 1. Resolve & clamp dimension scores ──────────────────────────────
        d_scores: Dict[Dimension, Decimal] = {}
        for dim in Dimension:
            raw = dimension_scores.get(dim.value, 50.0)
            d_scores[dim] = clamp(to_decimal(raw))

        ordered_scores   = [d_scores[d] for d in Dimension]
        ordered_weights  = [self.weights[d] for d in Dimension]

        # ── 2. Weighted mean (D_w) ────────────────────────────────────────────
        d_w = weighted_mean(ordered_scores, ordered_weights)
        d_w = clamp(d_w)

        # ── 3. Weighted std-dev & CV ──────────────────────────────────────────
        std = weighted_std_dev(ordered_scores, ordered_weights, d_w)
        cv  = coefficient_of_variation(std, d_w)

        # ── 4. Non-compensatory penalty ───────────────────────────────────────
        penalty = clamp(Decimal(1) - self.lambda_penalty * cv, Decimal(0), Decimal(1))

        # ── 5. Talent risk adjustment ─────────────────────────────────────────
        tc  = to_decimal(talent_concentration)
        tc_excess  = max(Decimal(0), tc - self.talent_threshold)
        tra = clamp(Decimal(1) - self.talent_risk_coeff * tc_excess, Decimal(0), Decimal(1))

        # ── 6. Final V^R ──────────────────────────────────────────────────────
        vr_score = clamp(d_w * penalty * tra)

        # ── 7. Per-dimension contributions ───────────────────────────────────
        contributions = {d.value: d_scores[d] * self.weights[d] for d in Dimension}

        result = VRResult(
            vr_score=vr_score,
            weighted_mean=d_w,
            std_dev=std,
            coefficient_of_variation=cv,
            penalty_factor=penalty,
            talent_concentration=tc,
            talent_risk_adjustment=tra,
            dimension_scores={d.value: d_scores[d] for d in Dimension},
            dimension_contributions=contributions,
        )

        logger.info("vr_calculated", **result.to_dict())
        return result
