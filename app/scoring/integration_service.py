"""
Full Pipeline Integration Service (Task 6.0b).

Orchestrates the Org-AI-R scoring pipeline by calling CS1 API (company, persist)
and CS2 API (evidence, signals). In a single-app deployment, cs1_api_url and
cs2_api_url may both point to the same base URL (e.g. http://localhost:8000).
"""

from decimal import Decimal
import logging
from typing import Any, Optional

import httpx

from app.pipelines.evidence_mapper.evidence_mapping_table import (
    EvidenceScore,
    SignalSource,
)

logger = logging.getLogger(__name__)


def _normalize_base_url(url: str) -> str:
    """Ensure base URL has no trailing slash."""
    return url.rstrip("/")


class ScoringIntegrationService:
    """
    Service that orchestrates the full scoring pipeline via HTTP:
    fetch company from CS1, evidence from CS2, run dimension scoring,
    TC → V^R → Position Factor → H^R → Synergy → Org-AI-R, persist to CS1.
    """

    def __init__(
        self,
        cs1_api_url: str,
        cs2_api_url: str,
        timeout: float = 60.0,
    ):
        self.cs1_api_url = _normalize_base_url(cs1_api_url)
        self.cs2_api_url = _normalize_base_url(cs2_api_url)
        self.timeout = timeout

    def score_company(self, ticker: str) -> dict[str, Any]:
        """
        Run the full Org-AI-R pipeline for a company identified by ticker.

        1. Fetch company from CS1
        2. Fetch evidence from CS2 (optional; used for evidence-score build)
        3. Collect Glassdoor and Board signals (from CS2 or already stored)
        4. Build EvidenceScore list (for audit; actual dimension scoring runs server-side)
        5. Trigger full pipeline (dimension scores → TC → V^R → PF → H^R → Synergy → Org-AI-R)
        6. Persist assessment to CS1

        Returns the Org-AI-R response as a dict.
        """
        company = self._fetch_company(ticker)
        company_id = str(company["id"])
        ticker_upper = (ticker or "").strip().upper()

        # Optional: fetch evidence and build evidence scores for audit
        cs2_evidence = self._fetch_cs2_evidence(company_id)
        glassdoor_signal = self._collect_glassdoor(company_id, ticker_upper)
        board_signal = self._collect_board(company_id, ticker_upper)
        evidence_scores = self._build_evidence_scores(cs2_evidence, glassdoor_signal, board_signal)
        if evidence_scores:
            logger.debug("Built %d evidence scores for company %s", len(evidence_scores), company_id)

        # Run full pipeline and persist (dimension scoring, TC, VR, PF, HR, Synergy, Org-AI-R)
        response = self._persist_assessment(company_id)
        if not response:
            raise RuntimeError(f"Failed to compute or persist Org-AI-R for company {company_id}")

        # Optional: compute alignment from returned dimension_scores for reference
        dim_scores = response.get("dimension_scores") or {}
        alignment = self._calculate_alignment(dim_scores)
        response["alignment"] = alignment

        return response

    def _fetch_company(self, ticker: str) -> dict[str, Any]:
        """Fetch company from CS1 by ticker. Returns company dict with id, name, ticker, etc."""
        ticker_upper = (ticker or "").strip().upper()
        if not ticker_upper:
            raise ValueError("Ticker is required")

        url = f"{self.cs1_api_url}/api/v1/companies"
        params = {"page": 1, "page_size": 100}
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
        items = data.get("items") or []
        for item in items:
            if (item.get("ticker") or "").strip().upper() == ticker_upper:
                return item
        raise LookupError(f"Company not found for ticker: {ticker}")

    def _fetch_cs2_evidence(self, company_id: str) -> dict[str, Any]:
        """Fetch evidence (documents, signals) for a company from CS2."""
        url = f"{self.cs2_api_url}/api/v1/companies/{company_id}/evidence"
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(url)
            r.raise_for_status()
            return r.json()

    def _collect_glassdoor(self, company_id: str, ticker: str) -> Optional[dict[str, Any]]:
        """Collect Glassdoor culture signal for the company (from CS2 signals)."""
        url = f"{self.cs2_api_url}/api/v1/companies/{company_id}/signals/glassdoor_reviews"
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(url)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            signals = r.json()
        if not signals:
            return None
        # Use first signal; if multiple, aggregate could be done here
        s = signals[0]
        return {
            "normalized_score": s.get("normalized_score", 0.0),
            "confidence": s.get("confidence", 0.0),
            "metadata": s.get("metadata") or {},
        }

    def _collect_board(self, company_id: str, ticker: str) -> Optional[dict[str, Any]]:
        """Collect Board composition signal for the company (from CS2 signals)."""
        url = f"{self.cs2_api_url}/api/v1/companies/{company_id}/signals/board_composition"
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(url)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            signals = r.json()
        if not signals:
            return None
        s = signals[0]
        return {
            "normalized_score": s.get("normalized_score", 0.0),
            "confidence": s.get("confidence", 0.0),
            "metadata": s.get("metadata") or {},
        }

    def _build_evidence_scores(
        self,
        cs2_evidence: dict[str, Any],
        glassdoor_signal: Optional[dict[str, Any]],
        board_signal: Optional[dict[str, Any]],
    ) -> list[EvidenceScore]:
        """Build EvidenceScore list from CS2 evidence and optional Glassdoor/Board signals."""
        from decimal import Decimal

        scores: list[EvidenceScore] = []

        # From CS2 evidence signals (category -> SignalSource by value)
        for sig in (cs2_evidence.get("signals") or []):
            cat = (sig.get("category") or "").strip()
            if not cat:
                continue
            try:
                source = SignalSource(cat)
            except ValueError:
                continue
            raw = float(sig.get("normalized_score") or 0.0)
            conf = float(sig.get("confidence") or 0.0)
            scores.append(
                EvidenceScore(
                    source=source,
                    raw_score=Decimal(str(max(0, min(100, raw)))),
                    confidence=Decimal(str(max(0, min(1, conf)))),
                    evidence_count=1,
                    metadata=sig.get("metadata") or {},
                )
            )

        sources_seen = {s.source for s in scores}
        if glassdoor_signal and SignalSource.GLASSDOOR_REVIEWS not in sources_seen:
            raw = float(glassdoor_signal.get("normalized_score") or 0.0)
            conf = float(glassdoor_signal.get("confidence") or 0.0)
            scores.append(
                EvidenceScore(
                    source=SignalSource.GLASSDOOR_REVIEWS,
                    raw_score=Decimal(str(max(0, min(100, raw)))),
                    confidence=Decimal(str(max(0, min(1, conf)))),
                    evidence_count=glassdoor_signal.get("metadata", {}).get("evidence_count", 1),
                    metadata=glassdoor_signal.get("metadata") or {},
                )
            )
            sources_seen.add(SignalSource.GLASSDOOR_REVIEWS)

        if board_signal and SignalSource.BOARD_COMPOSITION not in sources_seen:
            raw = float(board_signal.get("normalized_score") or 0.0)
            conf = float(board_signal.get("confidence") or 0.0)
            scores.append(
                EvidenceScore(
                    source=SignalSource.BOARD_COMPOSITION,
                    raw_score=Decimal(str(max(0, min(100, raw)))),
                    confidence=Decimal(str(max(0, min(1, conf)))),
                    evidence_count=1,
                    metadata=board_signal.get("metadata") or {},
                )
            )

        return scores

    def _calculate_alignment(self, dimension_scores: dict[str, float]) -> float:
        """Compute alignment from dimension scores (leadership_vision, ai_governance)."""
        leadership = dimension_scores.get("leadership_vision", 50.0)
        governance = dimension_scores.get("ai_governance", 50.0)
        raw = (0.6 * leadership + 0.4 * governance) / 100.0
        return max(0.5, min(0.95, raw))

    def _persist_assessment(self, company_id: str) -> Optional[dict[str, Any]]:
        """
        Run full pipeline (dimension scores, TC, V^R, PF, H^R, Synergy, Org-AI-R)
        and persist result to CS1. Returns the Org-AI-R response dict.
        """
        url = f"{self.cs1_api_url}/api/v1/scores/companies/{company_id}/compute-org-air"
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(url)
            r.raise_for_status()
            return r.json()
