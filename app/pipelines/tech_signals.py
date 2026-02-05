"""Technology stack signal collector."""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from app.models.signal import (
    ExternalSignalCreate,
    SignalCategory,
    SignalSource,
    TechnologyDetection,
)

logger = logging.getLogger(__name__)


class TechStackCollector:
    """Analyze company technology stacks for AI capabilities."""

    # Known AI-related technologies and their categories
    AI_TECHNOLOGIES = {
        # Cloud AI Services
        "aws sagemaker": "cloud_ml",
        "azure ml": "cloud_ml",
        "azure machine learning": "cloud_ml",
        "google vertex": "cloud_ml",
        "google cloud ai": "cloud_ml",
        "databricks": "cloud_ml",
        
        # ML Frameworks
        "tensorflow": "ml_framework",
        "pytorch": "ml_framework",
        "scikit-learn": "ml_framework",
        "keras": "ml_framework",
        "jax": "ml_framework",
        
        # Data Infrastructure
        "snowflake": "data_platform",
        "spark": "data_platform",
        "apache spark": "data_platform",
        "kafka": "data_platform",
        "airflow": "data_platform",
        
        # AI APIs
        "openai": "ai_api",
        "anthropic": "ai_api",
        "huggingface": "ai_api",
        "cohere": "ai_api",
        
        # ML Infrastructure
        "mlflow": "ml_infrastructure",
        "kubeflow": "ml_infrastructure",
        "ray": "ml_infrastructure",
        "weights and biases": "ml_infrastructure",
        "wandb": "ml_infrastructure",
    }

    def analyze_tech_stack(
        self,
        company_id: UUID,
        technologies: list[TechnologyDetection]
    ) -> ExternalSignalCreate:
        """
        Analyze technology stack for AI capabilities.
        
        Scoring (0-100):
        - Each AI technology: 10 points (max 50)
        - Each category covered: 12.5 points (max 50)
        """
        # Filter AI-related technologies
        ai_techs = [t for t in technologies if t.is_ai_related]
        
        # Score by category coverage
        categories_found = set(t.category for t in ai_techs)
        
        # Calculate scores
        tech_score = min(len(ai_techs) * 10, 50)
        category_score = min(len(categories_found) * 12.5, 50)
        
        score = tech_score + category_score

        return ExternalSignalCreate(
            company_id=company_id,
            category=SignalCategory.DIGITAL_PRESENCE,
            source=SignalSource.BUILTWITH,
            signal_date=datetime.now(timezone.utc),
            raw_value=f"{len(ai_techs)} AI technologies detected",
            normalized_score=round(score, 1),
            confidence=0.85,
            metadata={
                "ai_technologies": [t.name for t in ai_techs],
                "categories": list(categories_found),
                "total_technologies": len(technologies),
                "category_count": len(categories_found)
            }
        )

    def classify_technology(self, tech_name: str) -> TechnologyDetection:
        """Classify a technology as AI-related or not."""
        tech_lower = tech_name.lower()
        
        # Check if it's a known AI technology
        for ai_tech, category in self.AI_TECHNOLOGIES.items():
            if ai_tech in tech_lower or tech_lower in ai_tech:
                return TechnologyDetection(
                    name=tech_name,
                    category=category,
                    is_ai_related=True,
                    confidence=0.9
                )
        
        # Not a known AI technology
        return TechnologyDetection(
            name=tech_name,
            category="other",
            is_ai_related=False,
            confidence=0.7
        )

    def create_sample_technologies(
        self, 
        ai_maturity: str = "medium"
    ) -> list[TechnologyDetection]:
        """
        Create sample technology detections for testing/demo.
        
        Args:
            ai_maturity: "low", "medium", or "high"
        """
        # Base technologies (non-AI)
        base_techs = [
            TechnologyDetection(name="React", category="frontend", is_ai_related=False),
            TechnologyDetection(name="Node.js", category="backend", is_ai_related=False),
            TechnologyDetection(name="PostgreSQL", category="database", is_ai_related=False),
            TechnologyDetection(name="AWS", category="cloud", is_ai_related=False),
            TechnologyDetection(name="Docker", category="devops", is_ai_related=False),
        ]
        
        # AI technologies by maturity level
        low_ai_techs = [
            TechnologyDetection(name="Python", category="language", is_ai_related=False),
        ]
        
        medium_ai_techs = [
            TechnologyDetection(name="Snowflake", category="data_platform", is_ai_related=True),
            TechnologyDetection(name="Apache Spark", category="data_platform", is_ai_related=True),
        ]
        
        high_ai_techs = [
            TechnologyDetection(name="AWS SageMaker", category="cloud_ml", is_ai_related=True),
            TechnologyDetection(name="TensorFlow", category="ml_framework", is_ai_related=True),
            TechnologyDetection(name="OpenAI", category="ai_api", is_ai_related=True),
            TechnologyDetection(name="MLflow", category="ml_infrastructure", is_ai_related=True),
        ]
        
        if ai_maturity == "low":
            return base_techs + low_ai_techs
        elif ai_maturity == "medium":
            return base_techs + low_ai_techs + medium_ai_techs
        else:  # high
            return base_techs + low_ai_techs + medium_ai_techs + high_ai_techs