"""Evidence collection pipelines for PE Org-AI-R Platform."""

from app.pipelines.sec_edgar import SECEdgarPipeline
from app.pipelines.document_parser import DocumentParser
from app.pipelines.document_chunker import SemanticChunker
from app.pipelines.job_signals import JobSignalCollector
from app.pipelines.digital_presence_signals import (
    DigitalPresenceCollector,
    TechStackCollector,
    NewsSignalCollector,
)
from app.pipelines.patent_signals import PatentSignalCollector
from app.pipelines.leadership_signals import LeadershipSignalCollector
from app.pipelines.glassdoor_collector import fetch_reviews as fetch_glassdoor_reviews

__all__ = [
    "SECEdgarPipeline",
    "DocumentParser",
    "SemanticChunker",
    "JobSignalCollector",
    "DigitalPresenceCollector",
    "TechStackCollector",
    "NewsSignalCollector",
    "PatentSignalCollector",
    "LeadershipSignalCollector",
    "fetch_glassdoor_reviews",
]