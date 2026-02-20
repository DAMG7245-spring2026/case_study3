# PE Org-AI-R Platform - Case Study 2: Evidence Collection

AI Readiness Assessment Platform for Private Equity Portfolio Companies with automated SEC filings collection and external operational signals analysis.

## Links

- FastAPI public URL: http://35.93.9.162:8000/docs
- Demo video link: https://youtu.be/xpflYeUJdp0
- google colab doc: https://codelabs-preview.appspot.com/?file_id=1ObtcVTcTSMoM_9oB4PaTuLT-OJgGIZe-5PG6L3d2urw
- google docs: 

## 🎯 Project Overview

This platform automates the collection and analysis of evidence for AI readiness assessment across multiple portfolio companies. It combines:

- **SEC Filings Analysis**: Automated download, parsing, and section-aware chunking of 10-K, 10-Q, and 8-K filings
- **External Signals Collection**: Real-time operational metrics from jobs, tech stack, patents, and leadership data
- **Composite Scoring**: Weighted AI readiness scores across 4 signal categories
- **Cloud Storage**: Snowflake for structured data, optional S3 for raw document archival

### System Architecture

![Case Study 2 Architecture](docs/arch.png)

### Target Companies (10)

| Ticker | Company Name              | Industry            |
| ------ | ------------------------- | ------------------- |
| ADP    | Automatic Data Processing | Business Services   |
| CAT    | Caterpillar Inc.          | Manufacturing       |
| DE     | Deere & Company           | Manufacturing       |
| GS     | Goldman Sachs             | Financial Services  |
| HCA    | HCA Healthcare            | Healthcare Services |
| JPM    | JPMorgan Chase            | Financial Services  |
| PAYX   | Paychex Inc.              | Business Services   |
| TGT    | Target Corporation        | Retail              |
| UNH    | UnitedHealth Group        | Healthcare Services |
| WMT    | Walmart Inc.              | Retail              |

---

## 📋 Prerequisites

- **Python 3.11+** (project uses Python 3.11+ features)
- **Poetry 1.5+** for dependency management
  - Install: `curl -sSL https://install.python-poetry.org | python3 -`
- **Docker** (for Redis)
- **Snowflake account** with database and warehouse
  - Free trial: https://signup.snowflake.com/
- **AWS S3** (optional - for raw filing storage)

### Optional API Keys (for External Signals)

- **SERPAPI_KEY**: [SerpApi](https://serpapi.com/) for job postings data
- **BUILTWITH_API_KEY**: [BuiltWith Free API](https://api.builtwith.com/free-api) for tech stack
- **LENS_API_KEY**: [Lens.org](https://docs.api.lens.org/) for patent data
- **LINKEDIN_API_KEY**: Third-party API for leadership signals (optional)

**Note:** Pipeline runs with graceful degradation if API keys are missing.

---

## 🚀 Quick Start

```bash
# 1. Clone the repository
git clone <REPO_URL>
cd case_study2

# 2. Install dependencies
poetry install

# 3. Configure environment (see Configuration section below)

# Edit .env with your credentials

# 4. Start Redis
docker run -d --name redis-local -p 6379:6379 redis:7-alpine

# 5. Run database migrations
poetry run alembic upgrade head

# 6. Start the API server
poetry run uvicorn app.main:app --reload

# 7. Access interactive docs
# Open: http://127.0.0.1:8000/docs
```

**Verify setup:**

```bash
# Health check
curl http://localhost:8000/health

# Expected: {"status": "healthy", "version": "1.0.0"}
```

---

## ⚙️ Configuration

### 1. Snowflake Setup

#### Create Database and Warehouse

```sql
-- Connect to Snowflake Web UI: https://app.snowflake.com/

-- 1. Create warehouse
CREATE WAREHOUSE IF NOT EXISTS COMPUTE_WH WITH WAREHOUSE_SIZE = 'XSMALL';
USE WAREHOUSE COMPUTE_WH;

-- 2. Create database and schema
CREATE DATABASE IF NOT EXISTS PE_ORG_AIR;
USE DATABASE PE_ORG_AIR;
USE SCHEMA PUBLIC;

-- 3. Verify setup
SHOW DATABASES;
SHOW WAREHOUSES;
```

#### Insert Seed Data (Industries)

```sql
-- Required for company foreign key relationships
INSERT INTO industries (id, name, sector, h_r_base) VALUES
    ('550e8400-e29b-41d4-a716-446655440001', 'Manufacturing', 'Industrials', 72),
    ('550e8400-e29b-41d4-a716-446655440002', 'Healthcare Services', 'Healthcare', 78),
    ('550e8400-e29b-41d4-a716-446655440003', 'Business Services', 'Services', 75),
    ('550e8400-e29b-41d4-a716-446655440005', 'Financial Services', 'Financial', 80),
    ('550e8400-e29b-41d4-a716-446655440004', 'Retail', 'Consumer', 70);

-- Verify
SELECT * FROM industries;
```

#### Run Alembic Migrations

```bash
# Apply all migrations (creates tables: documents, document_chunks, external_signals, etc.)
poetry run alembic upgrade head

# Check current migration
poetry run alembic current

# Expected output: 003_add_company_signal_summaries (head)
```

### 2. Environment Variables

Create `.env` file in project root:

```bash
# ==============================================
# Application
# ==============================================
APP_NAME="PE Org-AI-R Platform"
APP_VERSION="1.0.0"
DEBUG=true

# ==============================================
# Snowflake (REQUIRED)
# ==============================================
SNOWFLAKE_ACCOUNT=xy12345.us-east-1  # Your account identifier
SNOWFLAKE_USER=your_username
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_DATABASE=PE_ORG_AIR
SNOWFLAKE_SCHEMA=PUBLIC
SNOWFLAKE_WAREHOUSE=COMPUTE_WH

# ==============================================
# Redis (REQUIRED for API caching)
# ==============================================
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# ==============================================
# AWS S3 (OPTIONAL - for raw filing storage)
# ==============================================
AWS_ACCESS_KEY_ID=your_access_key_id
AWS_SECRET_ACCESS_KEY=your_secret_access_key
AWS_REGION=us-east-1
S3_BUCKET=your-bucket-name

# ==============================================
# External API Keys (OPTIONAL - graceful degradation)
# ==============================================
# SerpAPI for job postings (technology_hiring signals)
SERPAPI_KEY=your_serpapi_key

# BuiltWith for tech stack (digital_presence signals)
BUILTWITH_API_KEY=your_builtwith_key

# Lens.org for patents (innovation_activity signals)
LENS_API_KEY=your_lens_token

# LinkedIn API for leadership (leadership_signals - optional)
LINKEDIN_API_KEY=your_linkedin_key
```

### 3. Redis Setup

```bash
# Option 1: Docker (Recommended)
docker run -d --name redis-local -p 6379:6379 redis:7-alpine

# Verify
docker ps | grep redis

# Option 2: Docker Compose
cd docker
docker-compose --env-file ../.env up -d
```

---

## 📊 Evidence Collection

### Using FastAPI Endpoints (Recommended)

**1. Start the API server:**

```bash
poetry run uvicorn app.main:app --reload
```

**2. Trigger evidence collection via API:**

```bash
# Collect SEC documents + external signals for specific companies
curl -X POST "http://localhost:8000/api/v1/evidence/backfill" \
  -H "Content-Type: application/json" \
  -d '{
    "tickers": ["JPM", "WMT", "GS"],
    "include_documents": true,
    "include_signals": true,
    "years_back": 3
  }'

# Response:
# {
#   "task_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
#   "status": "queued",
#   "companies_queued": 3,
#   "message": "Backfill started for 3 companies: JPM, WMT, GS"
# }
```

**3. Monitor progress:**

```bash
# Check overall statistics
curl "http://localhost:8000/api/v1/evidence/stats"

# View target companies
curl "http://localhost:8000/api/v1/target-companies"

# Get documents for a company
curl "http://localhost:8000/api/v1/documents?ticker=JPM"
```

### Using Command Line Script

```bash
# Collect for specific companies (documents + signals)
poetry run python scripts/collect_evidence.py --companies JPM,WMT,GS

# Documents only (faster)
poetry run python scripts/collect_evidence.py --companies CAT,DE,UNH --documents-only

# Signals only (no SEC downloads)
poetry run python scripts/collect_evidence.py --companies all --signals-only

# Custom parameters
poetry run python scripts/collect_evidence.py \
  --companies ADP,PAYX \
  --years-back 2 \
  --email your.email@university.edu
```

**Script Options:**

- `--companies <TICKERS>` – Comma-separated tickers or "all" (default: all 10 companies)
- `--documents-only` – Only collect SEC filings (skip external signals)
- `--signals-only` – Only collect external signals (skip SEC)
- `--years-back <N>` – Years of historical filings (default: 3, range: 1-10)
- `--email <EMAIL>` – SEC EDGAR email (default: student@university.edu)

---

## 📚 API Documentation

### Interactive Documentation

- **Swagger UI**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc
- **OpenAPI JSON**: http://127.0.0.1:8000/openapi.json

### Key Endpoints

#### Evidence Collection

```bash
# Trigger evidence collection (background task)
POST /api/v1/evidence/backfill
Body: {
  "tickers": ["JPM", "WMT"],      # Optional: omit for all companies
  "include_documents": true,       # Collect SEC filings
  "include_signals": true,         # Collect external signals
  "years_back": 3                  # Historical data range
}

# Get evidence statistics
GET /api/v1/evidence/stats

# Get company evidence (documents + signals)
GET /api/v1/companies/{company_id}/evidence

# Get target companies list
GET /api/v1/target-companies
```

#### Documents

```bash
# List documents
GET /api/v1/documents?ticker=JPM&limit=10

# Get document chunks
GET /api/v1/documents/{document_id}/chunks
```

#### Signals

```bash
# List signals for a company
GET /api/v1/signals?company_id={company_id}

# Get signal summary with composite score
GET /api/v1/companies/{company_id}/signals
```

#### Health Check

```bash
GET /health
# Response: {"status": "healthy", "version": "1.0.0"}
```

---

## 🗄️ Database Schema

### Core Tables (Alembic Migrations)

**Migration 001: Core Tables**

- `industries` – Industry baselines and sectors
- `companies` – Portfolio company information
- `assessments` – AI readiness assessment records
- `dimension_scores` – Detailed dimension-level scores

**Migration 002: Case Study 2 Extensions**

- `documents` – SEC filings metadata (10-K, 10-Q, 8-K)
- `document_chunks` – Section-aware text segments (~1000 words)
- `external_signals` – Operational readiness indicators

**Migration 003: Signal Summaries**

- `company_signal_summaries` – Aggregated AI readiness scores

### Key Tables Details

**documents:**

- Stores SEC filing metadata and status
- Fields: `id`, `company_id`, `ticker`, `filing_type`, `filing_date`, `content_hash`, `word_count`, `chunk_count`, `status`, `s3_key`
- Deduplication via `content_hash`

**document_chunks:**

- Section-aware text segments for LLM processing
- Fields: `id`, `document_id`, `chunk_index`, `content`, `section`, `start_char`, `end_char`, `word_count`
- Section examples: `item_1`, `item_1a`, `item_7`, `item_7a`

**external_signals:**

- Operational readiness metrics
- Fields: `id`, `company_id`, `category`, `source`, `signal_date`, `normalized_score` (0-100), `confidence` (0-1), `metadata` (JSON)
- Categories: `technology_hiring`, `digital_presence`, `innovation_activity`, `leadership_signals`

**company_signal_summaries:**

- Aggregated scores per company
- Fields: `company_id`, `ticker`, `technology_hiring_score`, `digital_presence_score`, `innovation_activity_score`, `leadership_signals_score`, `composite_score`, `signal_count`, `last_updated`
- Composite score weights: hiring 30%, digital 25%, innovation 25%, leadership 20%

---

## 🧪 Testing

### Run Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage report
poetry run pytest --cov=app --cov-report=term-missing

# Run specific test file
poetry run pytest tests/test_scores_coverage.py -v

# Run tests matching pattern
poetry run pytest -k "assessment" -v
```


### Coverage Summary (261 tests — all passing)

#### Target Modules

| Test File | Module | Statements | Coverage |
|---|---|---|---|
| `test_assessments_coverage.py` | `app/routers/assessments.py` | 102 | **98%** |
| `test_sec_edgar_coverage.py` | `app/pipelines/sec_edgar.py` | 113 | **97%** |
| `test_scores_coverage.py` | `app/routers/scores.py` | 203 | **89%** |
| `test_job_signals_coverage.py` | `app/pipelines/job_signals.py` | 208 | **82%** |

#### `test_scores_coverage.py` — Detailed Breakdown

| Class | Tests | Endpoints Covered |
|---|---|---|
| `TestUpdateDimensionScore` | 4 | `PUT /api/v1/scores/{score_id}` |
| `TestGetDimensionScores` | 4 | `GET /api/v1/scores/companies/{id}/dimension-scores` |
| `TestComputeDimensionScores` | 2 | `POST /api/v1/scores/companies/{id}/compute-dimension-scores` |
| `TestGetOrgAir` | 2 | `GET /api/v1/scores/companies/{id}/org-air` |
| `TestListOrgAir` | 3 | `GET /api/v1/scores/org-air` |
| `TestComputeOrgAir` | 3 | `POST /api/v1/scores/companies/{id}/compute-org-air` |
| `TestComputeAll` | 4 | `POST /api/v1/scores/companies/{id}/score-company` |
| `TestScoreByTicker` | 3 | `POST /api/v1/scores/score-by-ticker` |

#### `test_assessments_coverage.py` — Detailed Breakdown

| Class | Tests | Endpoints Covered |
|---|---|---|
| `TestListAssessments` | 6 | `GET /api/v1/assessments` (empty, filtered by company/status/type, with scores) |
| `TestGetAssessment` | 3 | `GET /api/v1/assessments/{id}` (cache miss, 404, with scores) |
| `TestUpdateAssessmentStatus` | 4 | `PATCH /api/v1/assessments/{id}/status` (valid/invalid transitions, 404) |
| `TestDimensionScoresViaAssessment` | 4 | `GET/POST /api/v1/assessments/{id}/scores` |

#### `test_job_signals_coverage.py` — Detailed Breakdown

| Class | Tests | Logic Covered |
|---|---|---|
| `TestPostedWithinDays` | 18 | All date string formats (`N days ago`, `N hours ago`, `N weeks ago`, `yesterday`, `month`, `year`, `N+ days`) |
| `TestClassifyPosting` | 5 | AI keyword detection, skill extraction |
| `TestIsTechJob` | 6 | Tech job title classification |
| `TestDedupePostings` | 5 | Title deduplication (case-insensitive, whitespace normalization) |
| `TestAnalyzeJobPostings` | 5 | Score calculation, `ExternalSignalCreate` output |
| `TestFetchPostings` | 8 | No API key, HTTP errors, date field fallbacks, empty title/desc skip |
| `TestFetchFromCareersPage` | 7 | Empty URL, non-200 status, HTML parsing, short title filter |
| `TestFetchFromJobspy` | 3 | ImportError fallback, exception handling |
| `TestCreateSamplePostings` | 3 | Low / medium / high AI focus |

#### `test_sec_edgar_coverage.py` — Detailed Breakdown

| Class | Tests | Logic Covered |
|---|---|---|
| `TestRateLimiter` | 7 | Init, `wait()` (sleep / no-sleep), `wait_async()` (sleep / no-sleep) |
| `TestSECEdgarPipeline` | 15 | Init, download success/empty, retry on rate-limit, all-retries-fail, filing type mapping (DEF-14A→DEFA14A), primary-document collection, `get_filing_path`, `list_downloaded_filings`, `download_all_companies`, async download |

---

## 🔍 Data Validation

### Snowflake Queries

**Check document collection status:**

```sql
SELECT
    ticker,
    filing_type,
    COUNT(*) as document_count,
    SUM(chunk_count) as total_chunks,
    MAX(filing_date) as latest_filing
FROM documents
WHERE ticker IN ('ADP', 'CAT', 'DE', 'GS', 'HCA', 'JPM', 'PAYX', 'TGT', 'UNH', 'WMT')
GROUP BY ticker, filing_type
ORDER BY ticker, filing_type;
```

**Check signal collection:**

```sql
SELECT
    c.ticker,
    COUNT(DISTINCT es.id) as signal_count,
    css.composite_score
FROM companies c
LEFT JOIN external_signals es ON c.id = es.company_id
LEFT JOIN company_signal_summaries css ON c.id = css.company_id
WHERE c.ticker IN ('ADP', 'CAT', 'DE', 'GS', 'HCA', 'JPM', 'PAYX', 'TGT', 'UNH', 'WMT')
GROUP BY c.ticker, css.composite_score
ORDER BY css.composite_score DESC;
```

**Verify section-aware chunking:**

```sql
SELECT
    d.ticker,
    d.filing_type,
    c.section,
    COUNT(*) as chunk_count
FROM document_chunks c
JOIN documents d ON c.document_id = d.id
WHERE d.ticker = 'JPM'
GROUP BY d.ticker, d.filing_type, c.section
ORDER BY d.filing_type, c.section;
```

---

## 🛠️ Development

### Project Structure

```
case_study2/
├── app/
│   ├── config.py                   # Settings (Snowflake, Redis, APIs)
│   ├── main.py                     # FastAPI application
│   ├── database/
│   │   ├── orm/                    # SQLAlchemy models
│   │   │   ├── document.py
│   │   │   ├── document_chunk.py
│   │   │   ├── external_signal.py
│   │   │   └── company_signal_summary.py
│   │   └── connection.py           # Snowflake connection
│   ├── models/
│   │   ├── document.py             # Pydantic models
│   │   ├── signal.py
│   │   └── evidence.py             # Evidence models (companies from DB)
│   ├── pipelines/
│   │   ├── sec_edgar.py            # SEC downloader
│   │   ├── document_parser.py      # iXBRL cleaning + section extraction
│   │   ├── document_chunker.py     # Semantic chunking
│   │   ├── job_signals.py          # SerpAPI + careers page
│   │   ├── digital_presence_signals.py  # BuiltWith + company news
│   │   ├── patent_signals.py       # Lens.org API
│   │   └── leadership_signals.py   # Website scraping
│   ├── routers/
│   │   ├── evidence.py             # /api/v1/evidence/*
│   │   ├── documents.py            # /api/v1/documents/*
│   │   └── signals.py              # /api/v1/signals/*
│   └── services/
│       ├── snowflake.py            # Database operations
│       └── s3_storage.py           # S3 uploads
├── scripts/
│   ├── collect_evidence.py         # CLI evidence collection
│   ├── backfill_companies.py       # Seed company data
│   └── generate_report.py          # Generate assessment reports
├── alembic/
│   ├── env.py                      # Alembic environment
│   └── versions/                   # Migration files
│       ├── 001_initial_core_tables.py
│       ├── 002_case_study_2_extensions.py
│       └── 003_add_company_signal_summaries.py
├── tests/
│   ├── test_document_parser.py
│   ├── test_document_chunker.py
│   └── ...
├── data/                           # Gitignored runtime data
│   ├── raw/sec/                    # Transient SEC downloads
│   └── evidence_summary.json       # Collection statistics
├── pyproject.toml                  # Poetry dependencies
├── alembic.ini                     # Alembic configuration
└── README.md
```

## 📐 Case Study 3: Org-AI-R Scoring Framework

Case Study 3 extends the evidence collection pipeline (CS2) with a full **Org-AI-R scoring framework** — computing V^R, H^R, Synergy, and composite Org-AI-R scores with SEM-based confidence intervals, new signal sources (Glassdoor / board composition), a Streamlit scoring dashboard, and an Airflow orchestration DAG.

### Scoring Formula

```
Org-AI-R = (1 - β) × [α × V^R + (1 - α) × H^R] + β × Synergy

Where:
  α = 0.60  (V^R weight)
  β = 0.12  (Synergy weight)

  V^R = WeightedMean(7 dimensions) × PenaltyFactor × TalentRiskAdj
  H^R = H^R_base × (1 + 0.15 × PositionFactor)
  Synergy = (V^R × H^R / 100) × Alignment × TimingFactor
  CI = score ± z × SEM  (Spearman-Brown reliability)
```

**Seven AI-Readiness Dimensions:**

| Dimension |
|---|
| Data Infrastructure 
| AI Governance
| Technology Stack
| Talent & Skills
| Leadership Vision 
| Use Case Portfolio
| Culture & Change

### CS3 New Modules

#### 1. Scoring Engine (`app/scoring/`)

Financial-grade scoring framework using `Decimal` arithmetic throughout:

| Module | Formula / Purpose |
|---|---|
| `utils.py` | Decimal conversion, clamp, weighted mean/std-dev, coefficient of variation |
| `vr_calculator.py` | **V^R** (Idiosyncratic Readiness): weighted 7-dimension mean with CV penalty and talent-risk adjustment |
| `talent_concentration.py` | **TC** (Talent Concentration / key-person risk): leadership ratio, team size, skill diversity, Glassdoor mentions |
| `position_factor.py` | **PF** (Position Factor): company position vs. sector peers using V^R deviation + market-cap percentile |
| `hr_calculator.py` | **H^R** (Systematic Opportunity): `H^R_base * (1 + 0.15 * PF)`, sector baselines |
| `synergy_calculator.py` | **Synergy**: `(V^R * H^R / 100) * alignment * timing_factor` |
| `confidence.py` | SEM-based confidence intervals using Spearman-Brown reliability (scipy-free `erfinv` / `norm_ppf`) |
| `org_air_calculator.py` | **Org-AI-R** composite: `(1-β)[α*V^R + (1-α)*H^R] + β*Synergy` with CI attachment |
| `integration_service.py` | Pipeline integration service orchestrating end-to-end scoring via API calls |

#### 2. Evidence Mapper (`app/pipelines/evidence_mapper/`)

Maps raw evidence signals to the 7 AI-readiness dimensions with weighted aggregation:

| Module | Purpose |
|---|---|
| `evidence_mapping_table.py` | Signal-to-dimension weight table (9 sources -> 7 dimensions), `build_signal_to_dimension_map()` for DB-driven weights, `compute_weights_hash()` for staleness detection |
| `evidence_mapper.py` | `EvidenceMapper`: weighted aggregation of evidence scores per dimension, coverage report generation |
| `rubric_scorer.py` | Rubric-based dimension scoring from evidence text |
| `score_rubric.py` | Score level definitions and rubric criteria |

#### 3. New Signal Sources

| Module | Signal |
|---|---|
| `app/pipelines/glassdoor_collector.py` | Glassdoor reviews -> culture/talent signals |
| `app/pipelines/board_analyzer.py` | Board composition -> AI governance signals |
| `scripts/load_glassdoor_from_file.py` | Bulk loader for Glassdoor data |

#### 4. Scoring Pipelines (`app/pipelines/`)

| Module | Purpose |
|---|---|
| `dimension_scorer.py` | Runs evidence mapper + rubric scorer to produce per-dimension scores |
| `org_air_pipeline.py` | End-to-end pipeline: dimensions -> V^R -> PF -> H^R -> Synergy -> Org-AI-R |

#### 5. Scoring API (`app/routers/scores.py`)

New endpoints for triggering and retrieving Org-AI-R scores:
- `PUT /api/v1/scores/{id}` -- update individual dimension score
- Score-by-ticker and full pipeline trigger endpoints
- Integration with all scoring calculators

#### 6. Streamlit Scoring Dashboard (`streamlit_ui/`)

Multi-page scoring dashboard (run with `poetry run streamlit run streamlit_ui/main.py`):

| Page | Function |
|---|---|
| `5_Scoring_Dashboard.py` | Overview of portfolio Org-AI-R scores |
| `6_Scoring_Evidence.py` | Evidence sources and coverage per company |
| `7_Scoring_Dimensions.py` | 7-dimension breakdown with radar charts |
| `8_Scoring_Portfolio.py` | Portfolio-level comparison and ranking |
| `9_Scoring_Audit.py` | Full audit trail (parameters, CI, sub-scores) |
| `10_Scoring_Calculator.py` | Interactive scoring calculator |

#### 7. Airflow Orchestration (`docker/airflow/dags/`)

`org_air_pipeline_dag.py` -- DAG that orchestrates the full pipeline:
1. Trigger document collection for all companies
2. Trigger signal collection (all categories including Glassdoor)
3. Compute signals per company
4. Run score-by-ticker for each company



---

## 👥 Team Member Contributions


### Individual Responsibilities

**WEI CHENG TU:**

- Transfer the signals and SEC file into score in 5 individual dimensions
- Evidence-to-Dimension Mapper
- Rubric-Based Scorer: get scores in 7 specific dimension for a company

**Nisarg Sheth:**

- Gather information for 2 dimensions that are new in this case study
- Glassdoor Culture Collector: for culture dimension
- Board Composition Analyzer: for AI Governance dimension
- Streamlit UI

**YU TZU LI:**
- Scoring calculator pipeline and API Endpoints
- Property-Based Tests

---
