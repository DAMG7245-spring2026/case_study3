# Scripts Directory

Standalone CLI scripts run from the **project root** via Poetry. They add `../` to `sys.path` so they can import from `app/`.

## Scripts

| Script                     | Purpose                                                                                                                                     |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `seed_target_companies.py` | Insert 10 target companies into Snowflake. Idempotent — skips existing tickers.                                                             |
| `collect_evidence.py`      | Main orchestrator: downloads SEC filings, parses+chunks docs, collects signals (jobs/patents/digital/leadership), upserts signal summaries. |
| `backfill_companies.py`    | Thin wrapper — fetches tickers from DB and calls `collect_evidence.main()` for all.                                                         |
| `generate_report.py`       | Reads `company_signal_summaries` from Snowflake, writes `docs/evidence_report.md` and `reports/external_signals_report.csv`.                |

## Key Flags for `collect_evidence.py`

```bash
--companies all|CAT,JPM,...   # default: all
--documents-only              # skip signals
--signals-only                # skip SEC download (fast)
--years-back N                # SEC filings lookback (default: 3)
```

## Prerequisites

- `.env` must be present at project root with Snowflake credentials.
- Companies must exist in DB before collecting evidence (`seed_target_companies.py` first).
- Optional API keys for richer signals: `SERPAPI_KEY`, `BUILTWITH_API_KEY`, `LENS_API_KEY`. Scripts degrade gracefully without them.

## Outputs

- SEC filings downloaded to `data/raw/sec/`
- Evidence summary JSON: `data/evidence_summary.json`
- Markdown report: `docs/evidence_report.md`
- CSV report: `reports/external_signals_report.csv` (gitignored)

## Composite Score Weights

`30% tech hiring + 25% innovation + 25% digital presence + 20% leadership`
