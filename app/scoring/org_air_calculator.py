"""Task 6.4: Org-AI-R (Organizational AI Readiness) Calculator.

Full formula
------------
  Org-AI-R = (1 − β) × [α × V^R + (1 − α) × H^R] + β × Synergy

  α = 0.60   (idiosyncratic / V^R weight)
  β = 0.12   (synergy weight)

The calculator:
  1. Accepts V^R, H^R, and Synergy results
  2. Applies the weighted aggregation
  3. Attaches an SEM-based confidence interval
  4. Logs a full audit trail via structlog
"""
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import structlog

from app.scoring.confidence import ConfidenceCalculator, ConfidenceInterval
from app.scoring.hr_calculator import HRResult
from app.scoring.synergy_calculator import SynergyResult
from app.scoring.utils import clamp, to_decimal
from app.scoring.vr_calculator import VRResult

logger = structlog.get_logger(__name__)

ALPHA: Decimal = Decimal("0.60")   # V^R weight
BETA:  Decimal = Decimal("0.12")   # Synergy weight
PARAM_VERSION = "3.0.0"           # δ=0.15, λ=0.25 corrected


@dataclass
class OrgAIRResult:
    """Complete Org-AI-R scoring result."""

    score_id:         str
    company_id:       str
    sector:           str
    timestamp:        datetime
    final_score:      Decimal
    vr_result:        VRResult
    hr_result:        HRResult
    synergy_result:   SynergyResult
    confidence_interval: ConfidenceInterval
    alpha:            Decimal
    beta:             Decimal
    parameter_version: str

    def to_dict(self) -> dict:
        return {
            "score_id":        self.score_id,
            "company_id":      self.company_id,
            "sector":          self.sector,
            "timestamp":       self.timestamp.isoformat(),
            "final_score":     float(self.final_score),
            "vr_score":        float(self.vr_result.vr_score),
            "hr_score":        float(self.hr_result.hr_score),
            "synergy_score":   float(self.synergy_result.synergy_score),
            "ci_lower":        float(self.confidence_interval.ci_lower),
            "ci_upper":        float(self.confidence_interval.ci_upper),
            "ci_width":        float(self.confidence_interval.ci_width),
            "sem":             float(self.confidence_interval.sem),
            "reliability":     float(self.confidence_interval.reliability),
            "evidence_count":  self.confidence_interval.evidence_count,
            "alpha":           float(self.alpha),
            "beta":            float(self.beta),
            "parameter_version": self.parameter_version,
        }


class OrgAIRCalculator:
    """Aggregate V^R, H^R, and Synergy into the final Org-AI-R score.

    Parameters
    ----------
    alpha:
        Weight for V^R in the aggregation formula (default 0.60).
    beta:
        Weight for Synergy (default 0.12).
    confidence_calculator:
        Provide a custom ConfidenceCalculator; if None a default is created.
    """

    def __init__(
        self,
        alpha: float = float(ALPHA),
        beta:  float = float(BETA),
        confidence_calculator: Optional[ConfidenceCalculator] = None,
    ) -> None:
        self.alpha = to_decimal(alpha)
        self.beta  = to_decimal(beta)
        self.ci_calc = confidence_calculator or ConfidenceCalculator()
        logger.info("org_air_calculator_initialized",
                    alpha=float(self.alpha), beta=float(self.beta))

    def calculate(
        self,
        company_id:     str,
        sector:         str,
        vr_result:      VRResult,
        hr_result:      HRResult,
        synergy_result: SynergyResult,
        evidence_count: int = 10,
        confidence_level: float = 0.95,
    ) -> OrgAIRResult:
        """Calculate Org-AI-R score.

        Args:
            company_id:      Company identifier.
            sector:          Company sector.
            vr_result:       Output of VRCalculator.calculate().
            hr_result:       Output of HRCalculator.calculate().
            synergy_result:  Output of SynergyCalculator.calculate().
            evidence_count:  Total evidence items (drives CI width).
            confidence_level: Desired CI coverage (default 0.95).

        Returns:
            OrgAIRResult with final score, sub-scores, CI, and audit trail.
        """
        score_id  = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)

        one_minus_beta = Decimal("1") - self.beta
        weighted = (
            self.alpha * vr_result.vr_score
            + (Decimal("1") - self.alpha) * hr_result.hr_score
        )
        final_score = clamp(one_minus_beta * weighted + self.beta * synergy_result.synergy_score)

        ci = self.ci_calc.calculate(
            score=final_score,
            score_type="org_air",
            evidence_count=evidence_count,
            confidence_level=confidence_level,
        )

        result = OrgAIRResult(
            score_id=score_id,
            company_id=company_id,
            sector=sector,
            timestamp=timestamp,
            final_score=final_score,
            vr_result=vr_result,
            hr_result=hr_result,
            synergy_result=synergy_result,
            confidence_interval=ci,
            alpha=self.alpha,
            beta=self.beta,
            parameter_version=PARAM_VERSION,
        )

        logger.info("org_air_calculated", **result.to_dict())
        return result
