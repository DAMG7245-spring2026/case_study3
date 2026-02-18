"""Task 6.0a: Position Factor Calculator.

Position Factor (PF) measures a company's position relative to sector peers.

  PF = +1.0  → clear industry leader
  PF =  0.0  → average position
  PF = -1.0  → industry laggard

Formula
-------
  PF = 0.6 × VR_component + 0.4 × MCap_component

Where:
  VR_component   = clamp((vr_score − sector_avg_vr) / 50, −1, 1)
  MCap_component = (market_cap_percentile − 0.5) × 2

Result bounded to [−1, 1].
"""
from decimal import Decimal
from typing import Dict, Optional

import structlog

from app.scoring.utils import clamp, to_decimal

logger = structlog.get_logger(__name__)

# Sector average V^R scores (from framework calibration data – PDF Table spec)
_SECTOR_AVG_VR: Dict[str, float] = {
    "technology": 65.0,
    "financial_services": 55.0,
    "healthcare": 52.0,
    "business_services": 50.0,
    "retail": 48.0,
    "manufacturing": 45.0,
}

_DEFAULT_SECTOR_AVG: float = 50.0
_VR_WEIGHT: Decimal = Decimal("0.6")
_MCAP_WEIGHT: Decimal = Decimal("0.4")


class PositionFactorCalculator:
    """Calculate position factor for use in H^R calculation.

    Parameters
    ----------
    sector_avg_vr:
        Override the built-in sector averages (for testing or recalibration).
    """

    def __init__(
        self,
        sector_avg_vr: Optional[Dict[str, float]] = None,
    ) -> None:
        self.sector_avg_vr = sector_avg_vr or _SECTOR_AVG_VR
        logger.info("position_factor_calculator_initialized",
                    sectors=list(self.sector_avg_vr.keys()))

    def calculate_position_factor(
        self,
        vr_score: float,
        sector: str,
        market_cap_percentile: float,
    ) -> Decimal:
        """Calculate position factor in [−1, 1].

        Args:
            vr_score: Company's V^R score (0–100).
            sector: Company sector (matched case-insensitively).
            market_cap_percentile: Position in sector by market cap (0–1;
                                   0 = smallest, 1 = largest).

        Returns:
            Position factor as Decimal bounded to [−1, 1].
        """
        sector_avg = self.sector_avg_vr.get(sector.lower(), _DEFAULT_SECTOR_AVG)

        # VR component: how far above/below sector average (normalised by 50)
        vr_diff = vr_score - sector_avg
        vr_component = clamp(
            to_decimal(vr_diff / 50.0),
            Decimal("-1"),
            Decimal("1"),
        )

        # Market-cap component: 0.5 percentile → 0, top → +1, bottom → -1
        mcap_component = to_decimal((market_cap_percentile - 0.5) * 2.0)

        pf_raw = _VR_WEIGHT * vr_component + _MCAP_WEIGHT * mcap_component
        pf = clamp(pf_raw, Decimal("-1"), Decimal("1"))

        logger.info(
            "position_factor_calculated",
            vr_score=vr_score,
            sector=sector,
            sector_avg=sector_avg,
            market_cap_percentile=market_cap_percentile,
            vr_component=float(vr_component),
            mcap_component=float(mcap_component),
            position_factor=float(pf),
        )
        return pf
