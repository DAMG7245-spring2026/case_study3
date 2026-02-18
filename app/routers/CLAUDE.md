# Routers — CLAUDE.md

## Files

| File | Prefix | Tag | Purpose |
|---|---|---|---|
| `health.py` | `/health` | Health | Dependency health checks (Snowflake, Redis, S3) |
| `companies.py` | `/api/v1/companies` | Companies | Company CRUD with Redis caching + soft-delete |
| `assessments.py` | `/api/v1/assessments` | Assessments | Assessment lifecycle with status state machine |
| `scores.py` | `/api/v1/scores` | Dimension Scores | Update individual dimension scores |
| `documents.py` | `/api/v1/documents` | documents | SEC filing collection → parse → chunk (background) |
| `signals.py` | `/api/v1` | signals | External signal collection + compute + list |
| `evidence.py` | `/api/v1` | evidence | Aggregate docs+signals; bulk backfill trigger |
| `report.py` | `/api/v1/report` | report | Composite score report (30/25/25/20 weights) |
| `industries.py` | `/api/v1/industries` | Industries | Industry lookup |
| `logs.py` | — | logs | In-memory log streaming endpoint |

## Request / Data Flow

```
Client
  │
  ├─ GET  /health                  → health.py       → Snowflake + Redis + S3 ping
  │
  ├─ CRUD /companies               → companies.py    → Snowflake (Redis cache on GET)
  │
  ├─ CRUD /assessments             → assessments.py  → status state machine
  │     └─ POST /{id}/scores                         → bulk insert dimension scores
  │
  ├─ PUT  /scores/{id}             → scores.py       → update single dimension score
  │
  ├─ POST /documents/collect       → documents.py    → [BackgroundTask]
  │     │                                               SECEdgarPipeline.download_filings()
  │     │                                               → DocumentParser.parse_filing()
  │     │                                               → SemanticChunker.chunk_document()
  │     │                                               → S3 upload + Snowflake insert
  │     └─ GET  /documents/collect/logs/{task_id}   → in-memory log stream
  │
  ├─ POST /signals/collect         → signals.py      → [BackgroundTask]
  │     │                                               stores raw data in signal_raw_collections
  │     ├─ POST /signals/compute                     → re-scores from stored raw data
  │     └─ GET  /signals/collect/logs/{task_id}      → in-memory log stream
  │
  ├─ GET  /companies/{id}/evidence → evidence.py     → joins documents + signals + summary
  ├─ POST /evidence/backfill       → evidence.py     → [BackgroundTask] full pipeline for N tickers
  │                                                     (docs + all 4 signal categories)
  │
  └─ GET  /report                  → report.py       → composite score from company_signal_summaries
                                                        Tech 30% + Innovation 25% + Digital 25% + Leadership 20%
```

## Assessment Status State Machine

```
DRAFT → IN_REVIEW → APPROVED
          │
          └→ REJECTED
```
Transitions enforced in `assessments.py` via `VALID_STATUS_TRANSITIONS` (from `app.models`).

## Signal Two-Step (Collect → Compute)

`signals.py` splits collection into two steps:
1. **Collect** (`POST /signals/collect`) — fetches raw data and stores it in `signal_raw_collections`
2. **Compute** (`POST /signals/compute`) — reads raw data, runs scoring logic, writes to `external_signals` and updates `company_signal_summaries`

Signal categories: `technology_hiring`, `innovation_activity`, `digital_presence`, `leadership_signals`, `glassdoor_reviews`

## Caching Pattern (companies + assessments)

```
GET request
  → Redis.get(cache_key)   # hit → return cached Pydantic model
  → Snowflake query        # miss → fetch, cache with TTL, return

Mutating request (PUT/DELETE/PATCH)
  → execute DB write
  → Redis.delete(cache_key)  # invalidate
```

## Key Dependencies

- `app.services.snowflake.SnowflakeService` — all DB I/O (via `get_snowflake_service`)
- `app.services.redis_cache.RedisCache` — caching (via `get_redis_cache`)
- `app.services.s3_storage.S3Storage` — filing uploads (via `get_s3_storage`)
- `app.pipelines.*` — imported lazily inside background tasks only
