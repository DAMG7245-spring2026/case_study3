# CLAUDE.md

## Project Overview

**PE Org-AI-R Platform** — AI Readiness Assessment for Private Equity.
Course project for DAMG7245 (Spring 2026) that evaluates companies' AI readiness by aggregating signals from job postings, SEC filings, patents, leadership profiles, and digital presence.

**Target Companies**: ADP, CAT, DE, GS, HCA, JPM, PAYX, TGT, UNH, WMT

## Tech Stack

- **Language**: Python 3.11+
- **Framework**: FastAPI (API), Streamlit (UI)
- **Package manager**: Poetry (`pyproject.toml`, `poetry.lock`)
- **Database**: Snowflake (data warehouse via SQLAlchemy + snowflake-connector-python)
- **Caching**: Redis (with configurable TTLs per resource type)
- **Storage**: AWS S3 (optional, for raw document archival via boto3)
- **Document parsing**: BeautifulSoup4, pdfplumber, WeasyPrint
- **SEC filings**: sec-edgar-downloader
- **Containers**: Docker / Docker Compose (`docker/`)
- **Secrets**: `.env` files loaded via `python-dotenv` (never committed)

## Project Structure

```
app/
  main.py                # FastAPI entrypoint with CORS, 8 routers, lifespan
  config.py              # Pydantic BaseSettings (Snowflake, Redis, S3, API keys, TTLs)
  database/
    connection.py        # SQLAlchemy engine for Snowflake
    base.py              # Declarative ORM base
    orm/                 # ORM models (company, assessment, dimension_score,
                         #   document, document_chunk, external_signal,
                         #   company_signal_summary, industry)
  models/                # Pydantic request/response models
    enums.py             # AssessmentType, AssessmentStatus, Dimension (7 dims)
    common.py            # PaginatedResponse, HealthResponse, ErrorResponse
    company.py           # CompanyCreate/Update/Response
    assessment.py        # AssessmentCreate/Response/StatusUpdate
    dimension.py         # DimensionScoreCreate/Update/Response
    document.py          # DocumentStatus, FilingType, DocumentResponse, ChunkResponse
    signal.py            # SignalCategory, SignalSource, JobPosting, Patent, etc.
    evidence.py          # BackfillRequest/Response, TARGET_COMPANIES dict
  routers/
    health.py            # Health checks (Snowflake, Redis, S3)
    companies.py         # Company CRUD with caching
    assessments.py       # Assessment lifecycle with status state machine
    scores.py            # Dimension score management
    documents.py         # SEC filing document collection & listing
    signals.py           # External signal collection (jobs, tech, patents, leadership)
    evidence.py          # Evidence aggregation + backfill endpoint
    report.py            # Weighted composite scoring report
  services/
    snowflake.py         # SnowflakeService: queries, health, document/signal helpers
    redis_cache.py       # RedisCache: Pydantic-aware caching with TTL
    s3_storage.py        # S3Storage: upload/download, graceful skip if unconfigured
  pipelines/
    sec_edgar.py         # SECEdgarPipeline: downloads SEC filings (rate-limited 8 req/s)
    document_parser.py   # DocumentParser: parses SEC filings, extracts ordered sections
    document_chunker.py  # SemanticChunker: paragraph-aware chunks (500 words, 50 overlap)
    job_signals.py       # JobSignalCollector: AI/ML hiring signal analysis
    leadership_signals.py    # LeadershipSignalCollector
    patent_signals.py        # PatentSignalCollector
    digital_presence_signals.py  # DigitalPresenceCollector, TechStackCollector, NewsSignalCollector
streamlit_app.py         # Streamlit dashboard (skeleton)
scripts/
  collect_evidence.py    # Evidence collection orchestrator for all pipelines
  backfill_companies.py  # Triggers evidence collection for all 10 target companies
  generate_report.py     # Generates markdown/CSV reports with composite scores
tests/
  conftest.py            # Fixtures
  test_api.py            # API endpoint tests
  test_models.py         # Pydantic model tests
  test_evidence_collection.py  # Evidence pipeline tests
  test_leadership_signals.py   # Leadership signal tests
alembic/                 # DB migrations (4 versions: core tables → CS2 extensions
                         #   → signal summaries → industries nullable fix)
docker/
  Dockerfile             # FastAPI app container
  docker-compose.yml     # API + Redis services
```

## Architecture Notes

- **Case Study 1**: Companies, Assessments, 7-dimension AI-readiness scoring with status state machine
- **Case Study 2**: SEC document collection → parsing → chunking; external signals (jobs, tech stack, patents, leadership, digital presence); evidence aggregation with composite scoring
- **Composite score weights**: 30% tech hiring, 25% innovation, 25% digital presence, 20% leadership
- **Document parser targets sections**: Item 1, 1A, 7, 7A from 10-K/10-Q filings
- **Graceful degradation**: Pipelines skip data sources when API keys are missing
- **Background tasks**: FastAPI BackgroundTasks for long-running evidence collection

## Environment Variables

Required in `.env`:

- **Snowflake**: `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, `SNOWFLAKE_DATABASE`, `SNOWFLAKE_SCHEMA`, `SNOWFLAKE_WAREHOUSE`
- **Redis**: `REDIS_HOST`, `REDIS_PORT`
- **AWS S3** (optional): `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME`
- **API keys** (optional): `SERPAPI_KEY`, `BUILTWITH_API_KEY`, `LENS_API_KEY`

## Team & Git Workflow

- Small team (2–3 people)
- Feature branches merged to `main` via PRs
- Main branch: `main`

## Coding Conventions

- General Python best practices (no enforced formatter; black/ruff/mypy configured in pyproject.toml)
- Pydantic v2 for data models
- FastAPI dependency injection patterns
- `structlog` for structured logging

## Testing

- Framework: `pytest` (with pytest-asyncio, pytest-cov, fakeredis)
- Tests live in `tests/` directory
- Run tests: `poetry run pytest`

## AI Assistant Rules

1. **Always run tests** before considering a change complete (`poetry run pytest`)
2. **Never commit without asking** — ask before every commit
3. **Explain changes for learning** — after making changes, walk through what was changed and why so the user can learn from each modification
4. **Keep changes minimal** — solve what's asked, avoid unnecessary refactoring
5. **Read before editing** — always read a file before modifying it
