# CLAUDE.md — streamlit_ui

## What this is

Streamlit frontend for the PE Org-AI-R Platform. Talks to the FastAPI backend via REST.

## Run

```bash
# From project root
poetry run streamlit run streamlit_ui/main.py

# Set backend URL (default: http://localhost:8000)
STREAMLIT_API_URL=http://<host>:8000 poetry run streamlit run streamlit_ui/main.py
```

## Structure

| Path | Purpose |
|---|---|
| `main.py` | App entry point, page config, nav description |
| `pages/` | One file per sidebar page (numbered 0–10) |
| `components/api_client.py` | All HTTP calls to the FastAPI backend |
| `components/scoring_sidebar.py` | Company selector + "Run Pipeline" sidebar widget |
| `components/json_viewer.py` | Collapsible JSON display helper |
| `utils/config.py` | `STREAMLIT_API_URL` / `STREAMLIT_API_TIMEOUT` env vars |
| `utils/target_companies.py` | Hard-coded target company list |

## Pages (sidebar order)

| File | Page |
|---|---|
| `0_Companies.py` | List / add / update companies |
| `1_Dashboard.py` | Evidence stats |
| `2_Documents.py` | SEC filings |
| `3_Signals.py` | External signals |
| `4_Evidence.py` | Full evidence per company |
| `5_Scoring_Dashboard.py` | Org-AI-R scores + 7-dimension chart |
| `6_Scoring_Evidence.py` | CS2/CS3 signal coverage |
| `7_Scoring_Dimensions.py` | Signal-to-dimension mapping |
| `8_Scoring_Portfolio.py` | Multi-company comparison |
| `9_Scoring_Audit.py` | Step-by-step pipeline audit |
| `10_Scoring_Calculator.py` | Manual V^R / H^R / Synergy / CI inputs |

## Guardrails

- Read a file before editing it.
- Keep changes minimal; do not refactor unless asked.
- Never commit without asking first.
- After changes, explain what changed and why.
