#!/usr/bin/env python
"""
Backfill evidence for all companies in the database.

Gets ticker list from Snowflake and runs evidence collection.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.snowflake import get_snowflake_service
from scripts.collect_evidence import main

if __name__ == "__main__":
    db = get_snowflake_service()
    rows = db.execute_query(
        "SELECT ticker, name FROM companies WHERE is_deleted = FALSE AND ticker IS NOT NULL ORDER BY ticker"
    )
    tickers = [r["ticker"] for r in (rows or []) if r.get("ticker")]

    print("\n" + "=" * 60)
    print("Backfilling Evidence for Companies in DB")
    print("=" * 60 + "\n")
    print(f"Processing {len(tickers)} companies from Snowflake:")
    for r in (rows or []):
        if r.get("ticker"):
            print(f"  - {r['ticker']}: {r.get('name', '')}")
    print("\n" + "=" * 60 + "\n")

    if not tickers:
        print("No companies in DB. Add them via the UI or run scripts/seed_target_companies.py")
        sys.exit(1)

    # Run collect_evidence with --companies ticker1,ticker2,...
    sys.argv = [sys.argv[0], "--companies", ",".join(tickers)]
    main()
