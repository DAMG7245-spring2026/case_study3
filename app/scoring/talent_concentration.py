"""Task 5.0e: Talent Concentration Calculator.

Talent Concentration (TC) measures key-person risk — how much AI capability
depends on a few individuals.

  TC = 0.0  → capability distributed across many people (low risk)
  TC = 1.0  → all capability in one person (maximum risk)

The TalentRiskAdj formula penalises high TC:
  TalentRiskAdj = 1 − 0.15 × max(0, TC − 0.25)
"""
import math
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Set

import structlog

from app.scoring.utils import clamp, to_decimal

logger = structlog.get_logger(__name__)


@dataclass
class JobAnalysis:
    """Categorised analysis of AI job postings."""

    total_ai_jobs: int
    senior_ai_jobs: int   # principal / staff / director / VP / head / chief
    mid_ai_jobs: int      # senior / lead / manager
    entry_ai_jobs: int    # junior / associate / entry / intern
    unique_skills: Set[str] = field(default_factory=set)


# Level classification keywords (lower-cased)
_SENIOR_KEYWORDS = {"principal", "staff", "director", "vp", "vice president",
                    "head of", "head,", "chief", "fellow"}
_MID_KEYWORDS    = {"senior", "lead", "manager", "sr."}
_ENTRY_KEYWORDS  = {"junior", "associate", "entry", "intern", "jr."}

# AI / ML role keywords used to decide whether a posting is AI-related
_AI_ROLE_KEYWORDS = {
    "machine learning", "ml engineer", "data scientist", "artificial intelligence",
    "deep learning", "nlp", "computer vision", "mlops", "ai engineer",
    "data engineer", "llm", "generative ai", "neural network",
}

# Skills we track for skill-concentration measurement
_TRACKED_SKILLS = {
    "python", "pytorch", "tensorflow", "scikit-learn", "spark", "hadoop",
    "kubernetes", "docker", "aws sagemaker", "azure ml", "gcp vertex",
    "huggingface", "langchain", "openai", "pandas", "numpy", "sql", "databricks",
    "mlflow", "kubeflow", "feature store", "model registry",
}


class TalentConcentrationCalculator:
    """Calculate talent concentration (key-person risk) from job and Glassdoor data.

    Formula
    -------
    TC = 0.4 * leadership_ratio
       + 0.3 * team_size_factor
       + 0.2 * skill_concentration
       + 0.1 * individual_mentions

    Where:
      leadership_ratio    = senior_jobs / total_jobs                (0–1)
      team_size_factor    = 1 / sqrt(total_jobs + 0.1), capped at 1  (smaller → higher TC)
      skill_concentration = 1 − (unique_skills / 15), clamped [0, 1]
      individual_mentions = glassdoor_mentions / reviews,   clamped [0, 1]

    Result is bounded to [0, 1].
    """

    LEADERSHIP_WEIGHT:   float = 0.4
    TEAM_SIZE_WEIGHT:    float = 0.3
    SKILL_CONC_WEIGHT:   float = 0.2
    INDIVIDUAL_WEIGHT:   float = 0.1

    SKILL_DIVERSITY_MAX: int   = 15   # ≥15 unique skills → low concentration
    TC_DEFAULT_IF_NO_DATA: float = 0.5

    def calculate_tc(
        self,
        job_analysis: JobAnalysis,
        glassdoor_individual_mentions: int = 0,
        glassdoor_review_count: int = 1,
    ) -> Decimal:
        """Calculate talent concentration ratio in [0, 1].

        Args:
            job_analysis: Categorised job-posting analysis.
            glassdoor_individual_mentions: Number of reviews mentioning specific people.
            glassdoor_review_count: Total Glassdoor reviews analysed.

        Returns:
            Talent concentration as Decimal in [0, 1], 4 d.p.
        """
        # ── leadership ratio ──────────────────────────────────────────────
        if job_analysis.total_ai_jobs > 0:
            leadership_ratio = job_analysis.senior_ai_jobs / job_analysis.total_ai_jobs
        else:
            leadership_ratio = self.TC_DEFAULT_IF_NO_DATA

        # ── team size factor ──────────────────────────────────────────────
        team_size_factor = min(
            1.0, 1.0 / math.sqrt(job_analysis.total_ai_jobs + 0.1)
        )

        # ── skill concentration ───────────────────────────────────────────
        unique = len(job_analysis.unique_skills)
        skill_concentration = max(0.0, 1.0 - unique / self.SKILL_DIVERSITY_MAX)

        # ── individual mention factor ─────────────────────────────────────
        review_count = max(1, glassdoor_review_count)
        individual_factor = min(1.0, glassdoor_individual_mentions / review_count)

        # ── weighted combination ──────────────────────────────────────────
        tc_raw = (
            self.LEADERSHIP_WEIGHT   * leadership_ratio
            + self.TEAM_SIZE_WEIGHT  * team_size_factor
            + self.SKILL_CONC_WEIGHT * skill_concentration
            + self.INDIVIDUAL_WEIGHT * individual_factor
        )

        tc = to_decimal(max(0.0, min(1.0, tc_raw)))

        logger.info(
            "tc_calculated",
            total_ai_jobs=job_analysis.total_ai_jobs,
            senior_ai_jobs=job_analysis.senior_ai_jobs,
            unique_skills=unique,
            leadership_ratio=round(leadership_ratio, 4),
            team_size_factor=round(team_size_factor, 4),
            skill_concentration=round(skill_concentration, 4),
            individual_factor=round(individual_factor, 4),
            tc=float(tc),
        )
        return tc

    def analyze_job_postings(self, postings: List[dict]) -> JobAnalysis:
        """Categorise job postings by seniority level.

        Expects each posting dict to have at least a ``"title"`` key,
        and optionally ``"description"`` and ``"ai_skills"``.

        Senior keywords : principal, staff, director, vp, head, chief
        Mid keywords    : senior, lead, manager
        Entry keywords  : junior, associate, entry, intern

        Args:
            postings: List of job-posting dicts (from CS2 job collector).

        Returns:
            JobAnalysis with seniority counts and unique skill set.
        """
        total_ai = senior = mid = entry = 0
        unique_skills: Set[str] = set()

        for posting in postings:
            title_raw  = posting.get("title", "") or ""
            desc_raw   = posting.get("description", "") or ""
            skills_raw = posting.get("ai_skills", []) or []

            title_lower = title_raw.lower()
            text_lower  = f"{title_lower} {desc_raw.lower()}"

            # Only count AI-related postings
            if not any(kw in text_lower for kw in _AI_ROLE_KEYWORDS):
                # Also accept if the posting was pre-classified
                if not posting.get("is_ai_related", False):
                    continue

            total_ai += 1

            # Classify seniority
            if any(kw in title_lower for kw in _SENIOR_KEYWORDS):
                senior += 1
            elif any(kw in title_lower for kw in _MID_KEYWORDS):
                mid += 1
            elif any(kw in title_lower for kw in _ENTRY_KEYWORDS):
                entry += 1
            # else: unclassified (still counted in total_ai)

            # Collect skills
            for skill in skills_raw:
                if skill.lower() in _TRACKED_SKILLS:
                    unique_skills.add(skill.lower())
            # also scan description for tracked skills
            for skill in _TRACKED_SKILLS:
                if skill in text_lower:
                    unique_skills.add(skill)

        analysis = JobAnalysis(
            total_ai_jobs=total_ai,
            senior_ai_jobs=senior,
            mid_ai_jobs=mid,
            entry_ai_jobs=entry,
            unique_skills=unique_skills,
        )
        logger.info(
            "job_postings_analyzed",
            total_postings=len(postings),
            total_ai=total_ai,
            senior=senior,
            mid=mid,
            entry=entry,
            unique_skills=len(unique_skills),
        )
        return analysis
