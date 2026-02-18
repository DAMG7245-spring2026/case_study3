"""scripts/compute_scores.py

Full Org-AI-R scoring pipeline – reads real data from Snowflake and writes
computed scores back to the assessments table.

Pipeline steps per company
--------------------------
1. Run DimensionScoringPipeline  → upsert 7 rows in dimension_scores
2. Fetch dimension scores        → Dict[str, float]
3. Analyse job postings          → TalentConcentration (TC)
4. Compute V^R                   → VRCalculator
5. Compute Position Factor       → PositionFactorCalculator
6. Compute H^R                   → HRCalculator (uses real h_r_base from industries)
7. Compute Synergy               → SynergyCalculator
8. Compute Org-AI-R + CI         → OrgAIRCalculator + ConfidenceCalculator
9. Upsert assessment             → assessments table

Usage
-----
    poetry run python scripts/compute_scores.py
"""

from __future__ import annotations

import json
import logging
import sys
from decimal import Decimal
from typing import Optional

import structlog

# ── app imports ───────────────────────────────────────────────────────────────
from app.pipelines.dimension_scorer import DimensionScoringPipeline
from app.scoring.confidence import ConfidenceCalculator
from app.scoring.hr_calculator import HRCalculator
from app.scoring.org_air_calculator import OrgAIRCalculator
from app.scoring.position_factor import PositionFactorCalculator
from app.scoring.synergy_calculator import SynergyCalculator
from app.scoring.talent_concentration import TalentConcentrationCalculator
from app.scoring.vr_calculator import VRCalculator
from app.services.snowflake import SnowflakeService

# ── logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=False,
)
log = structlog.get_logger("compute_scores")

# ── DB-sector → PositionFactorCalculator sector mapping ──────────────────────
# industry.sector (from DB) → PF sector key
SECTOR_MAP: dict[str, str] = {
    "Technology":  "technology",
    "Financial":   "financial_services",
    "Healthcare":  "healthcare",
    "Services":    "business_services",
    "Industrials": "manufacturing",
    "Consumer":    "retail",
    "Energy":      "business_services",
    "Real Estate": "business_services",
}

# Market-cap percentile within sector (approximate, from public data Feb 2026)
# 0 = smallest, 1 = largest in sector
MARKET_CAP_PCT: dict[str, float] = {
    "JPM":  0.90,   # largest US bank
    "GS":   0.60,
    "WMT":  0.90,   # largest US retailer
    "TGT":  0.55,
    "UNH":  0.95,   # largest US health insurer
    "HCA":  0.50,
    "CAT":  0.70,
    "DE":   0.65,
    "ADP":  0.80,
    "PAYX": 0.45,
}

# Alignment factor per company (0-1; reflects strategy-execution alignment)
# Derived from leadership_vision dimension confidence level
ALIGNMENT_DEFAULT = 0.80

# Timing factor (macro AI environment in Feb 2026 = slightly above neutral)
TIMING_FACTOR = 1.05


def _alignment_from_scores(dim_scores: dict[str, float]) -> float:
    """Derive alignment factor from leadership and governance scores.
    High leadership + high governance = better strategic alignment.
    """
    leadership = dim_scores.get("leadership_vision", 50.0)
    governance  = dim_scores.get("ai_governance", 50.0)
    raw = (0.6 * leadership + 0.4 * governance) / 100.0
    return max(0.5, min(0.95, raw))


def _build_sector_map(db: SnowflakeService) -> dict[str, dict]:
    """Return {industry_id: {name, sector, h_r_base}} from industries table."""
    rows = db.execute_query("SELECT id, name, sector, h_r_base FROM industries")
    return {r["id"]: r for r in rows}


def run_pipeline(tickers: Optional[list[str]] = None) -> list[dict]:
    """Run the full scoring pipeline for all (or selected) companies.

    Args:
        tickers: If given, only process these tickers.

    Returns:
        List of result dicts (one per company).
    """
    db = SnowflakeService()
    industries = _build_sector_map(db)

    # ── calculators (shared across companies) ─────────────────────────────────
    tc_calc    = TalentConcentrationCalculator()
    vr_calc    = VRCalculator()
    pf_calc    = PositionFactorCalculator()
    hr_calc    = HRCalculator()
    syn_calc   = SynergyCalculator()
    ci_calc    = ConfidenceCalculator()
    org_calc   = OrgAIRCalculator(confidence_calculator=ci_calc)
    dim_pipeline = DimensionScoringPipeline(db)

    # ── fetch companies ───────────────────────────────────────────────────────
    companies = db.execute_query(
        "SELECT id, name, ticker, industry_id, position_factor "
        "FROM companies WHERE is_deleted = FALSE ORDER BY name"
    )
    if tickers:
        upper = {t.upper() for t in tickers}
        companies = [c for c in companies if c["ticker"] in upper]

    results = []

    for co in companies:
        company_id   = co["id"]
        ticker       = co["ticker"]
        industry_row = industries.get(co["industry_id"], {})
        industry_name = industry_row.get("name", "Unknown")
        db_sector    = industry_row.get("sector", "Services")
        pf_sector    = SECTOR_MAP.get(db_sector, "business_services")
        h_r_base     = float(industry_row.get("h_r_base", 65.0))
        mcap_pct     = MARKET_CAP_PCT.get(ticker, 0.5)

        log.info("scoring_company", ticker=ticker, industry=industry_name,
                 sector=pf_sector, h_r_base=h_r_base)

        # ── Step 1: compute dimension scores (runs DimensionScoringPipeline) ──
        try:
            dim_pipeline.compute_and_store(company_id)
            log.info("dimension_scores_computed", ticker=ticker)
        except Exception as exc:
            log.warning("dimension_scoring_failed", ticker=ticker, error=str(exc))

        # ── Step 2: fetch dimension scores from DB ────────────────────────────
        dim_scores = db.get_dimension_scores(company_id)
        if not dim_scores:
            log.warning("no_dimension_scores", ticker=ticker,
                        msg="using all-50 default")
            dim_scores = {}

        evidence_count = max(1, db.get_evidence_count(company_id))

        # ── Step 3: talent concentration from raw job postings ────────────────
        job_postings = db.get_job_raw_payload(company_id)
        job_analysis = tc_calc.analyze_job_postings(job_postings)
        tc = tc_calc.calculate_tc(job_analysis)
        log.info("talent_concentration", ticker=ticker, tc=float(tc),
                 total_ai_jobs=job_analysis.total_ai_jobs)

        # ── Step 4: V^R ───────────────────────────────────────────────────────
        vr_result = vr_calc.calculate(dim_scores, float(tc))
        log.info("vr_calculated", ticker=ticker, vr=float(vr_result.vr_score))

        # ── Step 5: Position Factor ───────────────────────────────────────────
        pf = pf_calc.calculate_position_factor(
            vr_score=float(vr_result.vr_score),
            sector=pf_sector,
            market_cap_percentile=mcap_pct,
        )
        log.info("position_factor", ticker=ticker, pf=float(pf))

        # ── Step 6: H^R (uses real h_r_base from DB) ─────────────────────────
        hr_result = hr_calc.calculate(
            sector=pf_sector,
            position_factor=float(pf),
            baseline_override=h_r_base,
        )
        log.info("hr_calculated", ticker=ticker, hr=float(hr_result.hr_score))

        # ── Step 7: Synergy ───────────────────────────────────────────────────
        alignment = _alignment_from_scores(dim_scores)
        syn_result = syn_calc.calculate(
            vr_score=vr_result.vr_score,
            hr_score=hr_result.hr_score,
            alignment=alignment,
            timing_factor=TIMING_FACTOR,
        )
        log.info("synergy_calculated", ticker=ticker,
                 synergy=float(syn_result.synergy_score))

        # ── Step 8: Org-AI-R + CI ─────────────────────────────────────────────
        org_result = org_calc.calculate(
            company_id=company_id,
            sector=pf_sector,
            vr_result=vr_result,
            hr_result=hr_result,
            synergy_result=syn_result,
            evidence_count=evidence_count,
        )
        log.info(
            "org_air_calculated",
            ticker=ticker,
            final=float(org_result.final_score),
            ci_lower=float(org_result.confidence_interval.ci_lower),
            ci_upper=float(org_result.confidence_interval.ci_upper),
        )

        # ── Step 9: persist to assessments ───────────────────────────────────
        db.upsert_assessment(
            company_id=company_id,
            v_r_score=float(vr_result.vr_score),
            h_r_score=float(hr_result.hr_score),
            synergy=float(syn_result.synergy_score),
            org_air_score=float(org_result.final_score),
            confidence_lower=float(org_result.confidence_interval.ci_lower),
            confidence_upper=float(org_result.confidence_interval.ci_upper),
            position_factor=float(pf),
            talent_concentration=float(tc),
        )

        result = {
            "ticker":             ticker,
            "company":            co["name"],
            "industry":           industry_name,
            "sector":             pf_sector,
            "vr_score":           round(float(vr_result.vr_score), 2),
            "hr_score":           round(float(hr_result.hr_score), 2),
            "synergy_score":      round(float(syn_result.synergy_score), 2),
            "org_air_score":      round(float(org_result.final_score), 2),
            "ci_lower":           round(float(org_result.confidence_interval.ci_lower), 2),
            "ci_upper":           round(float(org_result.confidence_interval.ci_upper), 2),
            "talent_concentration": round(float(tc), 4),
            "position_factor":    round(float(pf), 4),
            "h_r_base":           h_r_base,
            "evidence_count":     evidence_count,
            "dimension_scores":   {k: round(v, 2) for k, v in dim_scores.items()},
        }
        results.append(result)

    db.disconnect()
    return results


def _print_table(results: list[dict]) -> None:
    """Pretty-print the scoring results."""
    header = f"{'Ticker':<6}  {'Company':<25}  {'V^R':>6}  {'H^R':>6}  {'Syn':>6}  {'OrgAIR':>7}  {'CI Lower':>8}  {'CI Upper':>8}  {'TC':>6}  {'PF':>6}"
    print("\n" + "=" * len(header))
    print(header)
    print("=" * len(header))
    for r in results:
        print(
            f"{r['ticker']:<6}  {r['company'][:25]:<25}  "
            f"{r['vr_score']:>6.2f}  {r['hr_score']:>6.2f}  "
            f"{r['synergy_score']:>6.2f}  {r['org_air_score']:>7.2f}  "
            f"{r['ci_lower']:>8.2f}  {r['ci_upper']:>8.2f}  "
            f"{r['talent_concentration']:>6.4f}  {r['position_factor']:>6.4f}"
        )
    print("=" * len(header))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Compute Org-AI-R scores from Snowflake data")
    parser.add_argument("--tickers", nargs="*", help="Limit to specific tickers")
    args = parser.parse_args()

    log.info("pipeline_started", tickers=args.tickers or "all")
    results = run_pipeline(tickers=args.tickers)
    _print_table(results)

    # Write JSON summary
    out_path = "data/org_air_scores.json"
    import os, pathlib
    pathlib.Path("data").mkdir(exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    log.info("results_written", path=out_path)
    print(f"\nFull results written to {out_path}")
