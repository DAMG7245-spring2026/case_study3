# CLAUDE.md (root)

## What this is

PE Org-AI-R Platform (DAMG7245 Spring 2026). FastAPI + Snowflake + Redis.
Goal: compute AI-readiness scores by aggregating SEC filings + external signals.

## Key commands

- Tests: `poetry run pytest`
- Run API: `poetry run uvicorn app.main:app --reload`
- Evidence: `poetry run python scripts/collect_evidence.py`

## Landmarks (jump points)

- API entry: `app/main.py`
- Settings: `app/config.py`
- Pipelines: `app/pipelines/`
- Routers: `app/routers/`
- Services: `app/services/`
- Tests: `tests/`

## Guardrails (must follow)

1. Always run tests before calling a change complete.
2. Never commit without asking me first.
3. Keep changes minimal; avoid refactors unless requested.
4. Read a file before editing it.
5. After changes, explain what changed and why.
