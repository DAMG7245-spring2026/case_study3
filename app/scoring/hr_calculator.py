"""Task 6.1: H^R (Systematic Opportunity) Calculator.

Formula (corrected δ = 0.15)
-----------------------------
  H^R = H^R_base × (1 + δ × PositionFactor)

Where:
  H^R_base     = industry baseline H^R score (stored in ``industries`` table)
  δ            = 0.15  (CORRECTED from earlier 0.5)
  PositionFactor = output of PositionFactorCalculator, in [−1, 1]

Result clamped to [0, 100].
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

import structlog

from app.scoring.utils import clamp, to_decimal

logger = structlog.get_logger(__name__)

DELTA: Decimal = Decimal("0.15")   # corrected position-adjustment factor

# Sector baseline H^R scores (industry-level baseline when DB is unavailable)
_SECTOR_HR_BASELINES = {
    "technology": 70.0,
    "financial_services": 60.0,
    "healthcare": 55.0,
    "business_services": 50.0,
    "retail": 48.0,
    "manufacturing": 45.0,
}
_DEFAULT_HR_BASELINE: float = 50.0


@dataclass
class HRResult:
    """H^R calculation result."""

    hr_score: Decimal
    baseline: Decimal
    position_factor: Decimal
    delta_used: Decimal

    def to_dict(self) -> dict:
        return {
            "hr_score": float(self.hr_score),
            "baseline": float(self.baseline),
            "position_factor": float(self.position_factor),
            "delta": float(self.delta_used),
        }


class HRCalculator:
    """Compute H^R (Systematic Opportunity) for a company.

    Parameters
    ----------
    sector_baselines:
        Override the built-in sector → baseline H^R mapping.
    delta:
        Override δ (default 0.15).
    """

    def __init__(
        self,
        sector_baselines: Optional[dict] = None,
        delta: float = float(DELTA),
    ) -> None:
        self.sector_baselines = sector_baselines or _SECTOR_HR_BASELINES
        self.delta = to_decimal(delta)
        logger.info("hr_calculator_initialized", delta=float(self.delta))

    def calculate(
        self,
        sector: str,
        position_factor: float,
        baseline_override: Optional[float] = None,
    ) -> HRResult:
        """Calculate H^R score.

        Args:
            sector: Company sector (matched case-insensitively).
            position_factor: PF in [−1, 1] from PositionFactorCalculator.
            baseline_override: Explicit baseline to use (e.g. from DB industries table).
                               If None, the sector default is used.

        Returns:
            HRResult with audit trail.
        """
        if baseline_override is not None:
            baseline = to_decimal(baseline_override)
        else:
            raw_base = self.sector_baselines.get(sector.lower(), _DEFAULT_HR_BASELINE)
            baseline = to_decimal(raw_base)

        pf = to_decimal(position_factor)
        hr_score = clamp(baseline * (Decimal("1") + self.delta * pf))

        result = HRResult(
            hr_score=hr_score,
            baseline=baseline,
            position_factor=pf,
            delta_used=self.delta,
        )
        logger.info("hr_calculated", **result.to_dict())
        return result
