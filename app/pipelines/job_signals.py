"""Job posting signal collector for AI hiring analysis."""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import httpx

from app.models.signal import (
    ExternalSignalCreate,
    JobPosting,
    SignalCategory,
    SignalSource,
)

logger = logging.getLogger(__name__)


class JobSignalCollector:
    """Collect and analyze job posting signals for AI hiring."""

    # Keywords indicating AI/ML related positions
    AI_KEYWORDS = [
        "machine learning", "ml engineer", "data scientist",
        "artificial intelligence", "deep learning", "nlp",
        "computer vision", "mlops", "ai engineer",
        "pytorch", "tensorflow", "llm", "large language model",
        "generative ai", "neural network", "data engineer"
    ]

    # Skills that indicate AI/ML capabilities
    AI_SKILLS = [
        "python", "pytorch", "tensorflow", "scikit-learn",
        "spark", "hadoop", "kubernetes", "docker",
        "aws sagemaker", "azure ml", "gcp vertex",
        "huggingface", "langchain", "openai",
        "pandas", "numpy", "sql", "databricks"
    ]

    def __init__(self):
        self.client = httpx.Client(
            timeout=30.0,
            headers={"User-Agent": "Mozilla/5.0 (compatible; research)"}
        )

    def analyze_job_postings(
        self,
        company: str,
        postings: list[JobPosting],
        company_id: Optional[UUID] = None
    ) -> ExternalSignalCreate:
        """
        Analyze job postings to calculate hiring signal score.
        
        Scoring (0-100):
        - AI job ratio * 60 (max 60 points)
        - Skill diversity: len(skills) / 10 * 20 (max 20 points)
        - Volume bonus: min(ai_jobs / 5, 1) * 20 (max 20 points)
        """
        # Classify all postings
        classified = [self.classify_posting(p) for p in postings]
        
        total_tech_jobs = len([p for p in classified if self._is_tech_job(p)])
        ai_jobs = len([p for p in classified if p.is_ai_related])

        # Calculate metrics
        ai_ratio = ai_jobs / total_tech_jobs if total_tech_jobs > 0 else 0

        # Collect all AI skills mentioned
        all_skills = set()
        for posting in classified:
            all_skills.update(posting.ai_skills)

        # Calculate score
        score = (
            min(ai_ratio * 60, 60) +
            min(len(all_skills) / 10, 1) * 20 +
            min(ai_jobs / 5, 1) * 20
        )

        # Calculate confidence based on sample size
        confidence = min(0.5 + total_tech_jobs / 100, 0.95)

        return ExternalSignalCreate(
            company_id=company_id or UUID("00000000-0000-0000-0000-000000000000"),
            category=SignalCategory.TECHNOLOGY_HIRING,
            source=SignalSource.INDEED,
            signal_date=datetime.now(timezone.utc),
            raw_value=f"{ai_jobs}/{total_tech_jobs} AI jobs",
            normalized_score=round(score, 1),
            confidence=round(confidence, 3),
            metadata={
                "company": company,
                "total_tech_jobs": total_tech_jobs,
                "ai_jobs": ai_jobs,
                "ai_ratio": round(ai_ratio, 3),
                "skills_found": list(all_skills),
                "total_postings_analyzed": len(postings)
            }
        )

    def classify_posting(self, posting: JobPosting) -> JobPosting:
        """Classify a job posting as AI-related or not."""
        text = f"{posting.title} {posting.description}".lower()

        # Check for AI keywords
        is_ai = any(kw in text for kw in self.AI_KEYWORDS)

        # Extract AI skills
        skills = [skill for skill in self.AI_SKILLS if skill in text]

        posting.is_ai_related = is_ai
        posting.ai_skills = skills

        return posting

    def _is_tech_job(self, posting: JobPosting) -> bool:
        """Check if posting is a technology job."""
        tech_keywords = [
            "engineer", "developer", "programmer", "software",
            "data", "analyst", "scientist", "technical",
            "architect", "devops", "sre", "platform"
        ]
        title_lower = posting.title.lower()
        return any(kw in title_lower for kw in tech_keywords)

    def create_sample_postings(self, company: str, ai_focus: str = "medium") -> list[JobPosting]:
        """
        Create sample job postings for testing/demo purposes.
        
        Args:
            company: Company name
            ai_focus: "low", "medium", or "high" AI hiring focus
        """
        base_postings = [
            JobPosting(
                title="Software Engineer",
                company=company,
                location="Remote",
                description="Build scalable web applications using Python and JavaScript.",
                source="sample",
                url="https://example.com/job/1"
            ),
            JobPosting(
                title="Data Analyst",
                company=company,
                location="New York, NY",
                description="Analyze business data using SQL and Python. Create dashboards.",
                source="sample",
                url="https://example.com/job/2"
            ),
            JobPosting(
                title="Product Manager",
                company=company,
                location="San Francisco, CA",
                description="Lead product strategy and roadmap for enterprise software.",
                source="sample",
                url="https://example.com/job/3"
            ),
        ]

        ai_postings = [
            JobPosting(
                title="Machine Learning Engineer",
                company=company,
                location="Remote",
                description="Build ML models using PyTorch and TensorFlow. Deploy on AWS SageMaker.",
                source="sample",
                url="https://example.com/job/4"
            ),
            JobPosting(
                title="Data Scientist - NLP",
                company=company,
                location="Seattle, WA",
                description="Develop NLP models using HuggingFace transformers and LangChain.",
                source="sample",
                url="https://example.com/job/5"
            ),
            JobPosting(
                title="AI Engineer",
                company=company,
                location="Austin, TX",
                description="Build generative AI applications using OpenAI and LLM technologies.",
                source="sample",
                url="https://example.com/job/6"
            ),
            JobPosting(
                title="MLOps Engineer",
                company=company,
                location="Remote",
                description="Deploy and monitor ML models. Kubernetes, Docker, MLflow expertise.",
                source="sample",
                url="https://example.com/job/7"
            ),
        ]

        if ai_focus == "low":
            return base_postings
        elif ai_focus == "medium":
            return base_postings + ai_postings[:2]
        else:  # high
            return base_postings + ai_postings

    def __del__(self):
        """Cleanup HTTP client."""
        if hasattr(self, 'client'):
            self.client.close()