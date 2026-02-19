"""Task 6.2: SEM-Based Confidence Interval Calculator.

Replaces fixed-width intervals with statistically sound, evidence-based CIs.

Formulas
--------
  Spearman-Brown reliability:
      ρ = (n × r) / (1 + (n − 1) × r)

  Standard Error of Measurement:
      SEM = σ × √(1 − ρ)

  Confidence Interval:
      CI = score ± z × SEM
      z  = standard normal quantile for (1 + confidence_level) / 2
"""
import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

import structlog

from app.scoring.utils import clamp, to_decimal


def _erfinv(y: float) -> float:
    """Inverse of erf (solve erf(x) = y for x) using Newton-Raphson. No scipy."""
    if y <= -1.0 or y >= 1.0:
        raise ValueError("y must be in (-1, 1)")
    k = 2.0 / math.sqrt(math.pi)
    x = 0.0
    for _ in range(50):
        err = math.erf(x) - y
        if abs(err) < 1e-12:
            return x
        x = x - err / (k * math.exp(-x * x))
    return x


def _norm_ppf(p: float) -> float:
    """Standard normal quantile (inverse CDF) without scipy.

    Returns z such that P(Z <= z) = p for Z ~ N(0, 1).
    Phi(z) = (1 + erf(z/sqrt(2)))/2 => z = sqrt(2)*erfinv(2*p - 1).
    """
    if p <= 0.0 or p >= 1.0:
        raise ValueError("p must be in (0, 1)")
    return math.sqrt(2.0) * _erfinv(2.0 * p - 1.0)

logger = structlog.get_logger(__name__)

# Population std-dev estimates by score type (domain calibration constants)
_POPULATION_SD: dict[str, Decimal] = {
    "vr":      Decimal("15.0"),
    "hr":      Decimal("12.0"),
    "synergy": Decimal("10.0"),
    "org_air": Decimal("14.0"),
}
_DEFAULT_SD: Decimal = Decimal("15.0")

# Average inter-item correlation (Spearman-Brown default)
_DEFAULT_ITEM_CORRELATION: Decimal = Decimal("0.30")
# Cap reliability below 1.0 to keep SEM > 0
_MAX_RELIABILITY: Decimal = Decimal("0.99")


@dataclass
class ConfidenceInterval:
    """SEM-based confidence interval details."""

    point_estimate:  Decimal
    ci_lower:        Decimal
    ci_upper:        Decimal
    sem:             Decimal
    reliability:     Decimal
    evidence_count:  int
    confidence_level: float

    @property
    def ci_width(self) -> Decimal:
        return self.ci_upper - self.ci_lower

    def to_dict(self) -> dict:
        return {
            "point_estimate": float(self.point_estimate),
            "ci_lower": float(self.ci_lower),
            "ci_upper": float(self.ci_upper),
            "sem": float(self.sem),
            "reliability": float(self.reliability),
            "evidence_count": self.evidence_count,
            "ci_width": float(self.ci_width),
            "confidence_level": self.confidence_level,
        }


class ConfidenceCalculator:
    """Calculate SEM-based confidence intervals for Org-AI-R component scores.

    Parameters
    ----------
    population_sd:
        Override the built-in σ map.
    default_item_correlation:
        Override the default inter-item correlation r (default 0.30).
    """

    def __init__(
        self,
        population_sd: Optional[dict] = None,
        default_item_correlation: float = float(_DEFAULT_ITEM_CORRELATION),
    ) -> None:
        self.population_sd = {
            k: to_decimal(v) for k, v in (population_sd or _POPULATION_SD).items()
        }
        self.default_r = to_decimal(default_item_correlation)
        logger.info("confidence_calculator_initialized",
                    default_r=float(self.default_r))

    def calculate(
        self,
        score: Decimal,
        score_type: str,
        evidence_count: int,
        item_correlation: Optional[float] = None,
        confidence_level: float = 0.95,
    ) -> ConfidenceInterval:
        """Calculate SEM-based CI.

        Args:
            score: Point estimate (e.g. final Org-AI-R score).
            score_type: One of "vr", "hr", "synergy", "org_air".
            evidence_count: Number of evidence items backing the score.
            item_correlation: Inter-item correlation r; if None uses default 0.30.
            confidence_level: Desired CI coverage (default 0.95).

        Returns:
            ConfidenceInterval with SEM and reliability details.
        """
        r = to_decimal(item_correlation) if item_correlation is not None else self.default_r
        n = max(1, evidence_count)

        # Spearman-Brown prophecy formula
        rho = (to_decimal(n) * r) / (Decimal("1") + (to_decimal(n) - Decimal("1")) * r)
        rho = clamp(rho, Decimal("0"), _MAX_RELIABILITY)

        sigma = self.population_sd.get(score_type.lower(), _DEFAULT_SD)
        sem = sigma * to_decimal(math.sqrt(float(Decimal("1") - rho)))

        # z-score for the desired confidence level (scipy-free)
        z = to_decimal(_norm_ppf((1.0 + confidence_level) / 2.0))

        margin   = z * sem
        ci_lower = clamp(score - margin)
        ci_upper = clamp(score + margin)

        ci = ConfidenceInterval(
            point_estimate=score,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            sem=sem,
            reliability=rho,
            evidence_count=n,
            confidence_level=confidence_level,
        )
        logger.info("confidence_interval_calculated", **ci.to_dict())
        return ci
