from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Dict, List


class ScoreLevel(Enum):
    LEVEL_5 = (80, 100, "Excellent")
    LEVEL_4 = (60, 79, "Good")
    LEVEL_3 = (40, 59, "Adequate")
    LEVEL_2 = (20, 39, "Developing")
    LEVEL_1 = (0, 19, "Nascent")

    @property
    def min_score(self):
        return self.value[0]

    @property
    def max_score(self):
        return self.value[1]


@dataclass
class RubricCriteria:
    """Criteria for a single rubric level."""

    level: ScoreLevel
    keywords: List[str]
    min_keyword_matches: int
    quantitative_threshold: float  # e.g., AI job ratio > 0.3


@dataclass
class RubricResult:
    """Result of rubric scoring."""

    dimension: str
    level: ScoreLevel
    score: Decimal
    matched_keywords: List[str]
    keyword_match_count: int
    confidence: Decimal
    rationale: str = ""


# ---------------------------------------------------------------------------
# DIMENSION_RUBRICS
# Keys match Dimension enum values (str).
# Each dimension has exactly 5 RubricCriteria, one per ScoreLevel (5→1).
# keywords  : terms to scan in raw signal text / metadata
# min_keyword_matches : how many keyword hits are required to qualify for
#                       this level (evaluated top-down; first match wins)
# quantitative_threshold : normalised signal score (0-1) that must ALSO be
#                          met to qualify (0.0 = no numeric gate)
# ---------------------------------------------------------------------------

DIMENSION_RUBRICS: Dict[str, List[RubricCriteria]] = {
    # ------------------------------------------------------------------
    # 1. DATA_INFRASTRUCTURE
    #    Sources: DIGITAL_PRESENCE (secondary), SEC_ITEM_1A (secondary),
    #             SEC_ITEM_7 (secondary)
    # ------------------------------------------------------------------
    "data_infrastructure": [
        RubricCriteria(
            level=ScoreLevel.LEVEL_5,
            keywords=[
                "data lakehouse",
                "data mesh",
                "feature store",
                "vector database",
                "real-time streaming",
                "petabyte",
                "data fabric",
                "unified data platform",
                "distributed computing",
                "kafka",
                "delta lake",
                "iceberg",
            ],
            min_keyword_matches=4,
            quantitative_threshold=0.80,
        ),
        RubricCriteria(
            level=ScoreLevel.LEVEL_4,
            keywords=[
                "data warehouse",
                "data lake",
                "data pipeline",
                "databricks",
                "snowflake",
                "spark",
                "data catalog",
                "data governance",
                "data quality",
                "ETL",
                "ELT",
                "cloud storage",
            ],
            min_keyword_matches=3,
            quantitative_threshold=0.60,
        ),
        RubricCriteria(
            level=ScoreLevel.LEVEL_3,
            keywords=[
                "database",
                "data integration",
                "SQL",
                "data platform",
                "business intelligence",
                "reporting",
                "analytics",
                "centralized data",
            ],
            min_keyword_matches=2,
            quantitative_threshold=0.40,
        ),
        RubricCriteria(
            level=ScoreLevel.LEVEL_2,
            keywords=[
                "data collection",
                "spreadsheet",
                "legacy system",
                "siloed data",
                "manual process",
                "limited access",
                "inconsistent data",
            ],
            min_keyword_matches=1,
            quantitative_threshold=0.20,
        ),
        RubricCriteria(
            level=ScoreLevel.LEVEL_1,
            keywords=[
                "no data strategy",
                "paper-based",
                "ad hoc",
                "unstructured",
                "no governance",
            ],
            min_keyword_matches=0,
            quantitative_threshold=0.0,
        ),
    ],
    # ------------------------------------------------------------------
    # 2. AI_GOVERNANCE
    #    Sources: SEC_ITEM_1A (primary), LEADERSHIP_SIGNALS (secondary)
    # ------------------------------------------------------------------
    "ai_governance": [
        RubricCriteria(
            level=ScoreLevel.LEVEL_5,
            keywords=[
                "ai ethics committee",
                "responsible ai",
                "algorithmic accountability",
                "model risk management",
                "ai audit",
                "bias mitigation",
                "explainability",
                "ai policy",
                "fairness framework",
                "model governance",
                "ai compliance",
            ],
            min_keyword_matches=4,
            quantitative_threshold=0.80,
        ),
        RubricCriteria(
            level=ScoreLevel.LEVEL_4,
            keywords=[
                "ai guidelines",
                "model monitoring",
                "fairness testing",
                "privacy by design",
                "ai oversight",
                "governance committee",
                "risk assessment",
                "AI risk",
                "model documentation",
            ],
            min_keyword_matches=3,
            quantitative_threshold=0.60,
        ),
        RubricCriteria(
            level=ScoreLevel.LEVEL_3,
            keywords=[
                "data privacy",
                "GDPR",
                "compliance",
                "security controls",
                "regulation",
                "ai policy",
                "model review",
                "oversight",
            ],
            min_keyword_matches=2,
            quantitative_threshold=0.40,
        ),
        RubricCriteria(
            level=ScoreLevel.LEVEL_2,
            keywords=[
                "limited oversight",
                "informal review",
                "ad hoc compliance",
                "basic privacy",
                "awareness of risk",
            ],
            min_keyword_matches=1,
            quantitative_threshold=0.20,
        ),
        RubricCriteria(
            level=ScoreLevel.LEVEL_1,
            keywords=[
                "no governance",
                "no policy",
                "unregulated",
                "no oversight",
                "reactive",
            ],
            min_keyword_matches=0,
            quantitative_threshold=0.0,
        ),
    ],
    # ------------------------------------------------------------------
    # 3. TECHNOLOGY_STACK
    #    Sources: TECHNOLOGY_HIRING (primary), DIGITAL_PRESENCE (primary),
    #             SEC_ITEM_1 (secondary)
    # ------------------------------------------------------------------
    "technology_stack": [
        RubricCriteria(
            level=ScoreLevel.LEVEL_5,
            keywords=[
                "MLOps",
                "kubernetes",
                "cloud-native ML",
                "model serving",
                "real-time inference",
                "LLM deployment",
                "GPU cluster",
                "AutoML",
                "vector search",
                "feature store",
                "ray",
                "kubeflow",
            ],
            min_keyword_matches=4,
            quantitative_threshold=0.80,
        ),
        RubricCriteria(
            level=ScoreLevel.LEVEL_4,
            keywords=[
                "SageMaker",
                "Vertex AI",
                "Azure ML",
                "TensorFlow",
                "PyTorch",
                "MLflow",
                "Databricks",
                "Airflow",
                "huggingface",
                "openai",
                "langchain",
                "anthropic",
            ],
            min_keyword_matches=3,
            quantitative_threshold=0.60,
        ),
        RubricCriteria(
            level=ScoreLevel.LEVEL_3,
            keywords=[
                "python",
                "scikit-learn",
                "cloud platform",
                "spark",
                "data engineering",
                "API",
                "basic machine learning",
                "analytics platform",
            ],
            min_keyword_matches=2,
            quantitative_threshold=0.40,
        ),
        RubricCriteria(
            level=ScoreLevel.LEVEL_2,
            keywords=[
                "basic analytics",
                "excel",
                "legacy tools",
                "on-premise",
                "limited cloud",
                "no ML tools",
            ],
            min_keyword_matches=1,
            quantitative_threshold=0.20,
        ),
        RubricCriteria(
            level=ScoreLevel.LEVEL_1,
            keywords=[
                "manual processes",
                "outdated tools",
                "no cloud",
                "no analytics",
                "spreadsheet only",
            ],
            min_keyword_matches=0,
            quantitative_threshold=0.0,
        ),
    ],
    # ------------------------------------------------------------------
    # 4. TALENT_SKILLS
    #    Sources: TECHNOLOGY_HIRING (secondary), GLASSDOOR_REVIEWS (secondary)
    # ------------------------------------------------------------------
    "talent_skills": [
        RubricCriteria(
            level=ScoreLevel.LEVEL_5,
            keywords=[
                "AI research team",
                "chief AI officer",
                "ML engineer",
                "data scientist",
                "NLP specialist",
                "AI architect",
                "PhD researcher",
                "applied AI",
                "deep learning expert",
                "LLM engineer",
                "MLOps engineer",
            ],
            min_keyword_matches=4,
            quantitative_threshold=0.80,
        ),
        RubricCriteria(
            level=ScoreLevel.LEVEL_4,
            keywords=[
                "data science team",
                "machine learning engineer",
                "data engineer",
                "AI talent",
                "analytics team",
                "AI hiring",
                "ML expertise",
                "computer vision",
                "reinforcement learning",
            ],
            min_keyword_matches=3,
            quantitative_threshold=0.60,
        ),
        RubricCriteria(
            level=ScoreLevel.LEVEL_3,
            keywords=[
                "data analyst",
                "software engineer",
                "technical team",
                "python developer",
                "analytics capability",
                "data skills",
            ],
            min_keyword_matches=2,
            quantitative_threshold=0.40,
        ),
        RubricCriteria(
            level=ScoreLevel.LEVEL_2,
            keywords=[
                "limited technical staff",
                "generalist team",
                "upskilling",
                "training program",
                "some data skills",
            ],
            min_keyword_matches=1,
            quantitative_threshold=0.20,
        ),
        RubricCriteria(
            level=ScoreLevel.LEVEL_1,
            keywords=[
                "no technical talent",
                "no data skills",
                "no AI hiring",
                "skills gap",
                "no data team",
            ],
            min_keyword_matches=0,
            quantitative_threshold=0.0,
        ),
    ],
    # ------------------------------------------------------------------
    # 5. LEADERSHIP_VISION
    #    Sources: SEC_ITEM_7 (primary), LEADERSHIP_SIGNALS (primary),
    #             BOARD_COMPOSITION (primary), SEC_ITEM_1 (secondary),
    #             GLASSDOOR_REVIEWS (secondary)
    # ------------------------------------------------------------------
    "leadership_vision": [
        RubricCriteria(
            level=ScoreLevel.LEVEL_5,
            keywords=[
                "chief AI officer",
                "CAIO",
                "AI strategy",
                "board AI committee",
                "AI vision",
                "AI roadmap",
                "executive AI commitment",
                "digital transformation agenda",
                "strategic AI priority",
                "AI-first",
                "technology-driven strategy",
            ],
            min_keyword_matches=4,
            quantitative_threshold=0.80,
        ),
        RubricCriteria(
            level=ScoreLevel.LEVEL_4,
            keywords=[
                "CTO",
                "chief digital officer",
                "technology committee",
                "AI initiative",
                "executive sponsor",
                "digital strategy",
                "leadership commitment",
                "CDO",
                "technology investment",
            ],
            min_keyword_matches=3,
            quantitative_threshold=0.60,
        ),
        RubricCriteria(
            level=ScoreLevel.LEVEL_3,
            keywords=[
                "digital awareness",
                "technology officer",
                "innovation focus",
                "data leadership",
                "technology governance",
                "executive team",
            ],
            min_keyword_matches=2,
            quantitative_threshold=0.40,
        ),
        RubricCriteria(
            level=ScoreLevel.LEVEL_2,
            keywords=[
                "limited executive support",
                "ad hoc technology decisions",
                "some digital awareness",
                "board",
                "officer",
            ],
            min_keyword_matches=1,
            quantitative_threshold=0.20,
        ),
        RubricCriteria(
            level=ScoreLevel.LEVEL_1,
            keywords=[
                "no digital leadership",
                "no technology strategy",
                "unfamiliar with AI",
                "no innovation agenda",
            ],
            min_keyword_matches=0,
            quantitative_threshold=0.0,
        ),
    ],
    # ------------------------------------------------------------------
    # 6. USE_CASE_PORTFOLIO
    #    Sources: SEC_ITEM_1 (primary), SEC_ITEM_7 (secondary)
    # ------------------------------------------------------------------
    "use_case_portfolio": [
        RubricCriteria(
            level=ScoreLevel.LEVEL_5,
            keywords=[
                "AI product",
                "ML in production",
                "generative AI",
                "deployed model",
                "AI-driven revenue",
                "predictive analytics at scale",
                "autonomous systems",
                "AI core business",
                "LLM application",
                "recommendation system at scale",
            ],
            min_keyword_matches=4,
            quantitative_threshold=0.80,
        ),
        RubricCriteria(
            level=ScoreLevel.LEVEL_4,
            keywords=[
                "AI pilot",
                "proof of concept",
                "automation",
                "recommendation system",
                "fraud detection",
                "NLP application",
                "AI tool deployment",
                "predictive model",
                "computer vision application",
            ],
            min_keyword_matches=3,
            quantitative_threshold=0.60,
        ),
        RubricCriteria(
            level=ScoreLevel.LEVEL_3,
            keywords=[
                "analytics",
                "reporting automation",
                "process optimization",
                "basic prediction",
                "rule-based automation",
                "RPA",
                "digital workflow",
            ],
            min_keyword_matches=2,
            quantitative_threshold=0.40,
        ),
        RubricCriteria(
            level=ScoreLevel.LEVEL_2,
            keywords=[
                "exploring AI",
                "experimenting",
                "early automation",
                "limited AI use",
                "proof of concept planned",
            ],
            min_keyword_matches=1,
            quantitative_threshold=0.20,
        ),
        RubricCriteria(
            level=ScoreLevel.LEVEL_1,
            keywords=[
                "no AI use cases",
                "manual processes",
                "no automation",
                "traditional methods only",
                "no digital initiatives",
            ],
            min_keyword_matches=0,
            quantitative_threshold=0.0,
        ),
    ],
    # ------------------------------------------------------------------
    # 7. CULTURE_CHANGE
    #    Sources: GLASSDOOR_REVIEWS (primary), LEADERSHIP_SIGNALS (secondary)
    # ------------------------------------------------------------------
    "culture_change": [
        RubricCriteria(
            level=ScoreLevel.LEVEL_5,
            keywords=[
                "data-driven culture",
                "AI-first",
                "innovation culture",
                "experimentation",
                "learning organization",
                "hackathon",
                "research culture",
                "fail fast",
                "psychological safety",
                "continuous improvement",
                "growth mindset",
            ],
            min_keyword_matches=4,
            quantitative_threshold=0.80,
        ),
        RubricCriteria(
            level=ScoreLevel.LEVEL_4,
            keywords=[
                "innovation encouraged",
                "continuous learning",
                "digital mindset",
                "data-informed decisions",
                "cross-functional collaboration",
                "technology adoption",
                "agile",
                "open to change",
            ],
            min_keyword_matches=3,
            quantitative_threshold=0.60,
        ),
        RubricCriteria(
            level=ScoreLevel.LEVEL_3,
            keywords=[
                "change management",
                "digital awareness",
                "some innovation",
                "technology friendly",
                "learning programs",
                "collaborative",
            ],
            min_keyword_matches=2,
            quantitative_threshold=0.40,
        ),
        RubricCriteria(
            level=ScoreLevel.LEVEL_2,
            keywords=[
                "resistance to change",
                "limited collaboration",
                "hierarchical",
                "risk-averse",
                "slow adoption",
            ],
            min_keyword_matches=1,
            quantitative_threshold=0.20,
        ),
        RubricCriteria(
            level=ScoreLevel.LEVEL_1,
            keywords=[
                "no innovation culture",
                "change resistant",
                "siloed",
                "traditional mindset",
                "no learning culture",
            ],
            min_keyword_matches=0,
            quantitative_threshold=0.0,
        ),
    ],
}
