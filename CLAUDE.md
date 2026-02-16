# CLAUDE.md

## Project Overview

**PE Org-AI-R Platform** — AI Readiness Assessment for Private Equity.
Course project for DAMG7245 (Spring 2026) that evaluates companies' AI readiness by aggregating signals from job postings, SEC filings, patents, leadership profiles, and digital presence.

## Tech Stack

- **Language**: Python 3.11+
- **Framework**: FastAPI (API), Streamlit (UI)
- **Package manager**: Poetry (`pyproject.toml`, `poetry.lock`)
- **Database**: Snowflake (data warehouse) + Redis (caching)
- **Containers**: Docker / Docker Compose (local deployment)
- **Secrets**: `.env` files loaded via `python-dotenv` (never committed)

## Project Structure

```
app/
  main.py              # FastAPI entrypoint
  config.py            # Settings / env config
  database/            # DB connection and queries
  models/              # Pydantic models
  routers/             # API route handlers
  services/            # Business logic
  pipelines/           # Data ingestion pipelines
    job_signals.py
    leadership_signals.py
    patent_signals.py
    sec_edgar.py
    digital_presence_signals.py
    document_parser.py
    document_chunker.py
streamlit_app.py       # Streamlit dashboard
scripts/               # Utility scripts
tests/                 # pytest test suite
alembic/               # DB migrations
data/                  # Local data files
docker/                # Docker configs
docs/                  # Documentation
```

## Team & Git Workflow

- Small team (2–3 people)
- Feature branches merged to `main` via PRs
- Main branch: `main`

## Coding Conventions

- General Python best practices (no enforced formatter)
- Pydantic v2 for data models
- FastAPI dependency injection patterns
- `structlog` for structured logging

## Testing

- Framework: `pytest`
- Tests live in `tests/` directory mirroring `app/` structure
- Run tests: `poetry run pytest`

## AI Assistant Rules

1. **Always run tests** before considering a change complete (`poetry run pytest`)
2. **Never commit without asking** — ask before every commit
3. **Explain changes for learning** — after making changes, walk through what was changed and why so the user can learn from each modification
4. **Keep changes minimal** — solve what's asked, avoid unnecessary refactoring
5. **Read before editing** — always read a file before modifying it
