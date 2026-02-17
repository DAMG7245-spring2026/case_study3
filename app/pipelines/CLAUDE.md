# CLAUDE.md (app/pipelines)

## Scope

Pipelines for SEC filings + external signals. Keep changes minimal and localized.

## Key files (entry points)

- sec_edgar.py: download SEC filings to data/raw/sec/sec-edgar-filings/<TICKER>/<TYPE>/
- document_parser.py: parse SGML/HTML/PDF into structured sections (Item 1/1A/7/7A)
- document_chunker.py: chunk per-section (target 500 words, 50 overlap, merge <100)
- job_signals.py / leadership_signals.py / patent_signals.py / digital_presence_signals.py / glassdoor_collector.py

## Critical pitfalls (must handle)

- SEC filings may include multiple <DOCUMENT> blocks with the same <TYPE> (e.g., 10-K/10-Q).
- Some same-TYPE documents are uuencoded binaries / embedded PDFs (e.g., "begin 644 ...pdf", "%PDF-").
- Never pass binary/uuencoded/PDF text to BeautifulSoup. Detect and skip before parsing.

## Behavioral rules

- SEC: enforce rate limit (target 8 req/s) and retries/backoff on 429.
- Collectors: graceful degradation — missing API key or request failure must NOT raise; return []/None and log reason.

## How to debug safely (avoid context blowups)

- Prefer grep/sed to inspect specific ranges; avoid reading huge raw filings end-to-end.
- When investigating parse bugs, capture a minimal fixture for tests (don’t commit giant filings).

## Verification

- Run relevant tests before done: `poetry run pytest -k parser` (or specific test module)
- If changing parsers, add regression test for the edge case you fixed.
