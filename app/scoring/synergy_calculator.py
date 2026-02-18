"""Task 6.3: Synergy Score Calculator.

Formula
-------
  Synergy = (V^R × H^R / 100) × Alignment × TimingFactor

  TimingFactor must be clamped to [0.8, 1.2].
  Result clamped to [0, 100].
"""
from dataclasses import dataclass
from decimal import Decimal

import structlog

from app.scoring.utils import clamp, to_decimal

logger = structlog.get_logger(__name__)

_TIMING_MIN: Decimal = Decimal("0.8")
_TIMING_MAX: Decimal = Decimal("1.2")


@dataclass
class SynergyResult:
    """Synergy calculation result."""

    synergy_score:    Decimal
    interaction:      Decimal   # V^R × H^R / 100 (before alignment & timing)
    alignment_factor: Decimal
    timing_factor:    Decimal   # after clamping

    def to_dict(self) -> dict:
        return {
            "synergy_score":    float(self.synergy_score),
            "interaction":      float(self.interaction),
            "alignment_factor": float(self.alignment_factor),
            "timing_factor":    float(self.timing_factor),
        }


class SynergyCalculator:
    """Calculate Synergy interaction between V^R and H^R."""

    def calculate(
        self,
        vr_score: Decimal,
        hr_score: Decimal,
        alignment: float,
        timing_factor: float = 1.0,
    ) -> SynergyResult:
        """Calculate Synergy.

        Args:
            vr_score: V^R score [0, 100].
            hr_score: H^R score [0, 100].
            alignment: Alignment factor in (0, 1]; reflects strategic alignment.
            timing_factor: Market timing multiplier; clamped to [0.8, 1.2].

        Returns:
            SynergyResult with full audit trail.
        """
        alignment_dec = to_decimal(alignment)
        timing_dec    = clamp(to_decimal(timing_factor), _TIMING_MIN, _TIMING_MAX)

        interaction   = (vr_score * hr_score) / Decimal("100")
        synergy_raw   = interaction * alignment_dec * timing_dec
        synergy_score = clamp(synergy_raw)

        result = SynergyResult(
            synergy_score=synergy_score,
            interaction=interaction,
            alignment_factor=alignment_dec,
            timing_factor=timing_dec,
        )
        logger.info("synergy_calculated", **result.to_dict())
        return result
