# Building the PE Org-AI-R Platform: AI Readiness Scoring for Private Equity

**Author:** Wei Cheng Tu, Nisarg Sheth, Yu Tzu Li
**Summary:** Step-by-step guide to setting up and running the PE Org-AI-R Platform — a FastAPI + Snowflake + Redis system that computes AI-readiness scores for private equity portfolio companies using SEC filings, external signals, and the Org-AI-R scoring formula.
**Category:** Data Engineering, AI/ML, FinTech
**Status:** Draft
**Feedback Link:** https://github.com/DAMG7245-spring2026/case_study3/issues

---

## 1. Overview

In this codelab you will build and run the PE Org-AI-R Platform — an end-to-end AI-readiness assessment system for private equity portfolio companies.

**What you'll learn:**

- How to ingest SEC filings (10-K, 10-Q, 8-K) via SEC EDGAR and chunk them into section-aware segments
- How to collect four categories of external operational signals (jobs, tech stack, patents, leadership)
- How the Org-AI-R formula combines seven AI-readiness dimensions into a single composite score
- How to operate a FastAPI backend, Redis cache, Snowflake data warehouse, Streamlit dashboard, and Airflow DAG together

**What you'll build:**

A running instance of the platform with:
- REST API (FastAPI) at `http://localhost:8000`
- Scoring dashboard (Streamlit) at `http://localhost:8501`
- Pipeline orchestration (Airflow) at `http://localhost:8080`

**Target companies:** ADP, CAT, DE, GS, HCA, JPM, PAYX, TGT, UNH, WMT

---

## 2. Prerequisites

> **Duration:** 5 minutes

Before starting, make sure you have the following installed and accounts created.

### Software

- Python 3.11+
- Poetry 1.5+ — dependency manager
- Docker Desktop — for Redis, Airflow
- Git

### Accounts & API Keys (Required)

- **Snowflake** — Free trial at https://signup.snowflake.com/
- **AWS S3 bucket** (optional — for raw filing archival)

### External API Keys (Optional — graceful degradation if missing)

| Key | Service | Signal Category |
|---|---|---|
| `SERPAPI_KEY` | SerpApi | Job postings |
| `BUILTWITH_API_KEY` | BuiltWith | Tech stack |
| `LENS_API_KEY` | Lens.org | Patents |
| `LINKEDIN_API_KEY` | LinkedIn | Leadership |

> **Note:** The pipeline runs with graceful degradation. Missing API keys result in empty signal collections, not errors.

---

## 3. Clone the Repository and Install Dependencies

> **Duration:** 5 minutes

### Clone and install

```bash
# Clone the repository
git clone https://github.com/DAMG7245-spring2026/case_study3.git
cd case_study3

# Install Poetry (if not installed)
curl -sSL https://install.python-poetry.org | python3 -

# Install all project dependencies
poetry install
```

### Verify installation

```bash
poetry run python -c "import fastapi; print('FastAPI OK')"
poetry run python -c "import snowflake.connector; print('Snowflake OK')"
```

Expected output:
```
FastAPI OK
Snowflake OK
```

---

## 4. Configure the Environment

> **Duration:** 10 minutes

### Create the .env file

```bash
cp .env.example .env   # if template exists, otherwise create manually
```

Open `.env` and set the following values:

```bash
# ── Application ──────────────────────────────────────────────
APP_NAME="PE Org-AI-R Platform"
APP_VERSION="1.0.0"
DEBUG=true

# ── Snowflake (REQUIRED) ─────────────────────────────────────
SNOWFLAKE_ACCOUNT=xy12345.us-east-1
SNOWFLAKE_USER=your_username
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_DATABASE=PE_ORG_AIR
SNOWFLAKE_SCHEMA=PUBLIC
SNOWFLAKE_WAREHOUSE=COMPUTE_WH

# ── Redis (REQUIRED) ─────────────────────────────────────────
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# ── AWS S3 (OPTIONAL) ────────────────────────────────────────
AWS_ACCESS_KEY_ID=your_access_key_id
AWS_SECRET_ACCESS_KEY=your_secret_access_key
AWS_REGION=us-east-1
S3_BUCKET=your-bucket-name

# ── External API Keys (OPTIONAL) ─────────────────────────────
SERPAPI_KEY=your_serpapi_key
BUILTWITH_API_KEY=your_builtwith_key
LENS_API_KEY=your_lens_token
LINKEDIN_API_KEY=your_linkedin_key
```

### Snowflake setup

Log in to https://app.snowflake.com and run:

```sql
-- 1. Create warehouse
CREATE WAREHOUSE IF NOT EXISTS COMPUTE_WH WITH WAREHOUSE_SIZE = 'XSMALL';
USE WAREHOUSE COMPUTE_WH;

-- 2. Create database and schema
CREATE DATABASE IF NOT EXISTS PE_ORG_AIR;
USE DATABASE PE_ORG_AIR;
USE SCHEMA PUBLIC;

-- 3. Verify
SHOW DATABASES;
SHOW WAREHOUSES;
```

---

## 5. Set Up the Database

> **Duration:** 10 minutes

### Start Redis

```bash
# Option A: standalone Docker container
docker run -d --name redis-local -p 6379:6379 redis:7-alpine

# Verify Redis is running
docker ps | grep redis
```

### Run Alembic migrations

The migrations create all necessary tables in Snowflake.

```bash
poetry run alembic upgrade head

# Verify current migration
poetry run alembic current
# Expected: 013_signal_dimension_weights (head)
```

### Seed industry data

Open the Snowflake Web UI and run:

```sql
INSERT INTO industries (id, name, sector, h_r_base) VALUES
  ('550e8400-e29b-41d4-a716-446655440001', 'Manufacturing',       'Industrials', 72),
  ('550e8400-e29b-41d4-a716-446655440002', 'Healthcare Services', 'Healthcare',  78),
  ('550e8400-e29b-41d4-a716-446655440003', 'Business Services',   'Services',    75),
  ('550e8400-e29b-41d4-a716-446655440004', 'Retail',              'Consumer',    70),
  ('550e8400-e29b-41d4-a716-446655440005', 'Financial Services',  'Financial',   80);

SELECT * FROM industries;
```

### Seed portfolio companies

```bash
poetry run python scripts/seed_target_companies.py
```

### Database schema overview

| Table | Purpose |
|---|---|
| `industries` | Sector baselines and H^R starting values |
| `companies` | Portfolio company information |
| `assessments` | AI readiness assessment records |
| `dimension_scores` | Per-dimension scores (7 dimensions) |
| `documents` | SEC filing metadata (10-K, 10-Q, 8-K) |
| `document_chunks` | Section-aware text segments (~500 words) |
| `external_signals` | Raw operational signals with normalized scores |
| `company_signal_summaries` | Aggregated composite signal scores |

---

## 6. Start the Platform

> **Duration:** 5 minutes

### Option A: Start services individually

```bash
# Terminal 1 — FastAPI backend
poetry run uvicorn app.main:app --reload

# Terminal 2 — Streamlit dashboard
poetry run streamlit run streamlit_ui/main.py
```

### Option B: Docker Compose (all services)

```bash
cd docker
docker-compose --env-file ../.env up -d

# View logs
docker-compose logs -f api
```

### Verify the API is running

```bash
curl http://localhost:8000/health
# Expected: {"status": "healthy", "version": "1.0.0"}
```

You can now open:

| Service | URL |
|---|---|
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| Streamlit dashboard | http://localhost:8501 |
| Airflow | http://localhost:8080 (admin / admin) |

---

## 7. Collect Evidence

> **Duration:** 15 minutes

Evidence collection has two parts: SEC filings and external signals.

### Trigger via API

```bash
# Collect both SEC documents and external signals for three companies
curl -X POST "http://localhost:8000/api/v1/evidence/backfill" \
  -H "Content-Type: application/json" \
  -d '{
    "tickers": ["JPM", "WMT", "GS"],
    "include_documents": true,
    "include_signals": true,
    "years_back": 3
  }'

# Example response:
# {
#   "task_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
#   "status": "queued",
#   "companies_queued": 3,
#   "message": "Backfill started for 3 companies: JPM, WMT, GS"
# }

# Monitor progress
curl http://localhost:8000/api/v1/evidence/stats
```

### Trigger via CLI script

```bash
# All 10 companies — documents + signals
poetry run python scripts/collect_evidence.py --companies all

# Documents only (faster, no API keys needed)
poetry run python scripts/collect_evidence.py \
  --companies JPM,WMT,GS \
  --documents-only

# Signals only
poetry run python scripts/collect_evidence.py \
  --companies JPM,WMT \
  --signals-only
```

### Four external signal categories

| Category | Source | Weight |
|---|---|---|
| `technology_hiring` | SerpApi job ads | 30% |
| `digital_presence` | BuiltWith | 25% |
| `innovation_activity` | Lens.org patents | 25% |
| `leadership_signals` | Website / LinkedIn | 20% |

### New signals in Case Study 3

```bash
# Load Glassdoor culture/talent data from a local file
poetry run python scripts/load_glassdoor_from_file.py \
  --file data/glassdoor_export.json
```

The Board Composition Analyzer automatically pulls AI-governance signals from company proxy filings via the SEC EDGAR pipeline and stores them as dimension scores for the `ai_governance` dimension.

### Validate collected evidence in Snowflake

```sql
-- Document count by company and filing type
SELECT ticker, filing_type, COUNT(*) AS docs, SUM(chunk_count) AS chunks
FROM documents
WHERE ticker IN ('JPM','WMT','GS')
GROUP BY ticker, filing_type
ORDER BY ticker, filing_type;

-- Composite signal score per company
SELECT c.ticker, css.composite_score, css.signal_count
FROM companies c
JOIN company_signal_summaries css ON c.id = css.company_id
ORDER BY css.composite_score DESC;
```

---

## 8. Understand the Org-AI-R Scoring Formula

> **Duration:** 10 minutes

### Seven AI-Readiness Dimensions

All scoring starts from these seven dimensions, each scored 0–100.

| Dimension | Key Evidence Sources |
|---|---|
| Data Infrastructure | SEC filings Item 7, tech signals |
| AI Governance | Board composition, proxy filings |
| Technology Stack | BuiltWith, job postings |
| Talent & Skills | Job postings (AI/ML roles), Glassdoor |
| Leadership Vision | SEC Item 1, leadership signals |
| Use Case Portfolio | SEC 8-K, patent filings |
| Culture & Change | Glassdoor reviews, Glassdoor ratings |

### The Org-AI-R formula

```
Org-AI-R = (1 − β) × [α × V^R + (1 − α) × H^R] + β × Synergy

Where:
  α    = 0.60   (V^R weight vs H^R)
  β    = 0.12   (Synergy component weight)

  V^R      = WeightedMean(7 dimensions) × PenaltyFactor × TalentRiskAdj
  H^R      = H^R_base × (1 + 0.15 × PositionFactor)
  Synergy  = (V^R × H^R / 100) × Alignment × TimingFactor
  CI       = score ± z × SEM   (Spearman-Brown reliability, 95%)
```

### Sub-score definitions

| Sub-score | Meaning |
|---|---|
| **V^R** (Idiosyncratic) | Company-specific AI readiness based on internal evidence |
| **H^R** (Systematic) | Sector-level opportunity baseline adjusted by market position |
| **Synergy** | Multiplicative benefit when V^R and H^R are both high |
| **TC** (Talent Concentration) | Key-person / talent-concentration risk (lowers V^R) |
| **PF** (Position Factor) | Company rank vs. sector peers by V^R and market cap |
| **CI** (Confidence Interval) | 95% interval driven by evidence count via SEM |

### Sector H^R baselines

| Sector | H^R Base |
|---|---|
| Financial | 80 |
| Healthcare | 78 |
| Business Services | 75 |
| Manufacturing | 72 |
| Retail | 70 |

---

## 9. Compute Org-AI-R Scores

> **Duration:** 10 minutes

### Option A: Score a single company via the API

```bash
# Score by company UUID
curl -X POST \
  "http://localhost:8000/api/v1/scores/{company_id}/compute" \
  -H "Content-Type: application/json"

# Or score by ticker
curl -X POST \
  "http://localhost:8000/api/v1/scores/by-ticker/JPM" \
  -H "Content-Type: application/json"

# Example response:
# {
#   "ticker": "JPM",
#   "org_air_score": 74.35,
#   "vr_score": 72.10,
#   "hr_score": 81.20,
#   "synergy_score": 58.44,
#   "confidence_lower": 69.82,
#   "confidence_upper": 78.88,
#   "dimension_scores": {
#     "data_infrastructure": 78.5,
#     "ai_governance": 71.0,
#     "technology_stack": 76.2,
#     "talent_skills": 68.9,
#     "leadership_vision": 74.3,
#     "use_case_portfolio": 65.1,
#     "culture_change": 69.8
#   }
# }
```

### Option B: Batch score all companies via CLI

```bash
poetry run python scripts/compute_scores.py

# Output:
# Scoring JPM ... done  (74.35)
# Scoring WMT ... done  (66.12)
# ...
# Portfolio mean Org-AI-R: 71.4
```

### Option C: Interactive scoring calculator (Streamlit)

Open `http://localhost:8501`, navigate to page **"10 Scoring Calculator"**, and manually adjust dimension sliders to explore the formula live.

### How the pipeline runs internally

```
1. Load company + industry from Snowflake
2. Load dimension_scores (already computed by dimension_scorer)
3. Analyze job postings → TalentConcentration (TC)
4. V^R     = VRCalculator(dimension_scores, TC)
5. PF      = PositionFactorCalculator(V^R, sector, market_cap_percentile)
6. H^R     = HRCalculator(sector, PF, H^R_base)
7. Synergy = SynergyCalculator(V^R, H^R, alignment, timing_factor=1.05)
8. Org-AI-R = OrgAIRCalculator(V^R, H^R, Synergy)
9. Attach 95% CI using Spearman-Brown SEM
10. Return OrgAIRScores dataclass
```

---

## 10. Explore the Streamlit Dashboard

> **Duration:** 5 minutes

Navigate to `http://localhost:8501`. The dashboard has the following pages:

| Page | What it shows |
|---|---|
| 0 Companies | Portfolio company list and metadata |
| 1 Dashboard | Top-level portfolio health summary |
| 2 Documents | SEC filings index per company |
| 3 Signals | External signal breakdown (4 categories) |
| 4 Evidence | Evidence coverage and source stats |
| 5 Scoring Dashboard | Portfolio-wide Org-AI-R overview with rankings |
| 6 Scoring Evidence | Evidence sources and coverage heatmap per company |
| 7 Scoring Dimensions | Radar chart of 7 dimensions per company |
| 8 Scoring Portfolio | Side-by-side company comparison |
| 9 Scoring Audit | Full audit trail: parameters, CI, all sub-scores |
| 10 Scoring Calculator | Interactive slider-based formula explorer |

### Example: Viewing JPM's dimension radar chart

1. Open the Streamlit app at `http://localhost:8501`
2. Navigate to **"7 Scoring Dimensions"**
3. Select **"JPM"** from the company dropdown
4. The radar chart shows all seven dimensions with scores overlaid on the sector average

---

## 11. Airflow Orchestration

> **Duration:** 10 minutes

The Airflow DAG automates the full data pipeline on a schedule.

### Start Airflow (Docker Compose)

```bash
cd docker
docker-compose --env-file ../.env up -d airflow-db airflow-init
# Wait for init to complete, then:
docker-compose --env-file ../.env up -d airflow-webserver airflow-scheduler

# Open Airflow UI
open http://localhost:8080
# Login: admin / admin
```

### DAG: org_air_pipeline

The DAG `org_air_pipeline_dag.py` runs these tasks in sequence:

```
Task 1: collect_documents
  └─ POST /api/v1/evidence/backfill
     (include_documents=true, include_signals=false)

Task 2: collect_signals
  └─ POST /api/v1/evidence/backfill
     (include_documents=false, include_signals=true)
     Includes: job_signals, patent_signals, glassdoor_collector, board_analyzer

Task 3: compute_dimension_scores
  └─ Runs dimension_scorer for each company
     Maps evidence → 7 AI-readiness dimensions via evidence_mapper

Task 4: compute_org_air_scores
  └─ Runs org_air_pipeline for each company
     Persists V^R, H^R, Synergy, Org-AI-R to Snowflake
```

### Trigger the DAG manually

```bash
# Via CLI inside the container
docker exec -it docker-airflow-scheduler-1 \
  airflow dags trigger org_air_pipeline
```

Or use the Airflow UI:
1. Open `http://localhost:8080`
2. Find **"org_air_pipeline"**
3. Click the **▶ Trigger DAG** button

---

## 12. Run the Tests

> **Duration:** 5 minutes

Always run tests before marking any change as complete.

```bash
# Run the full test suite
poetry run pytest

# Run with coverage report
poetry run pytest --cov=app --cov-report=term-missing

# Run a specific test file
poetry run pytest tests/test_scoring_properties.py -v

# Run tests matching a keyword
poetry run pytest -k "org_air" -v
```

### Key test files

| Test File | Coverage |
|---|---|
| `test_scoring_properties.py` | Property-based tests for all scoring calculators |
| `test_board_analyzer.py` | Board composition → AI governance signals |
| `test_glassdoor_culture.py` | Glassdoor data → culture/talent signals |
| `test_leadership_signals.py` | Leadership signal collection |
| `test_evidence_collection.py` | SEC evidence ingestion end-to-end |
| `test_api.py` | FastAPI endpoint tests |
| `test_models.py` | Pydantic model validation |

---

## 13. Key API Reference

> **Duration:** 3 minutes

```bash
# ── Health ────────────────────────────────────────────────────
GET  /health

# ── Companies ─────────────────────────────────────────────────
GET  /api/v1/companies
GET  /api/v1/companies/{id}

# ── Evidence Collection ───────────────────────────────────────
POST /api/v1/evidence/backfill
GET  /api/v1/evidence/stats
GET  /api/v1/companies/{id}/evidence

# ── SEC Documents ─────────────────────────────────────────────
GET  /api/v1/documents?ticker=JPM&limit=10
GET  /api/v1/documents/{id}/chunks

# ── External Signals ──────────────────────────────────────────
GET  /api/v1/signals?company_id={id}
GET  /api/v1/companies/{id}/signals

# ── Scoring ───────────────────────────────────────────────────
POST /api/v1/scores/{id}/compute
POST /api/v1/scores/by-ticker/{ticker}
PUT  /api/v1/scores/{id}
GET  /api/v1/scores/{id}

# ── Assessments ───────────────────────────────────────────────
GET  /api/v1/assessments
POST /api/v1/assessments
```

Full interactive documentation: `http://localhost:8000/docs`

---

## 14. Congratulations!

You have successfully:

- Set up the PE Org-AI-R Platform (FastAPI + Snowflake + Redis + Streamlit + Airflow)
- Collected SEC filings and external operational signals for 10 portfolio companies
- Understood the Org-AI-R scoring formula and its seven dimensions
- Computed V^R, H^R, Synergy, and composite Org-AI-R scores with 95% confidence intervals
- Explored the multi-page Streamlit dashboard
- Orchestrated the pipeline with Apache Airflow
- Run the property-based test suite

### Team contributions

| Member | Contribution |
|---|---|
| Wei Cheng Tu | Evidence-to-Dimension Mapper, Rubric-Based Scorer (5 dimensions → scores) |
| Nisarg Sheth | Glassdoor Culture Collector (culture dimension), Board Composition Analyzer (AI governance dimension) |
| Yu Tzu Li | Scoring calculator pipeline, API endpoints, property-based tests |

### Resources

- FastAPI public URL: http://35.93.9.162:8000/docs
- Demo video: https://www.youtube.com/watch?v=ATQqYbEYGnM
- GitHub repository: https://github.com/DAMG7245-spring2026/case_study3
- Snowflake free trial: https://signup.snowflake.com/
