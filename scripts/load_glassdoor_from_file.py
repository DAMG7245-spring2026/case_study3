#!/usr/bin/env python
"""
Load Glassdoor reviews from a JSON file into the app's raw collection for a company.

Reads a file (default: data/NVDA.json), extracts the 'reviews' array or uses the root
if it's already a list, resolves company_id by ticker via the API, and PUTs the reviews
to PUT /api/v1/companies/{company_id}/raw/glassdoor_reviews.

Usage:
  poetry run python scripts/load_glassdoor_from_file.py
  poetry run python scripts/load_glassdoor_from_file.py --file data/NVDA.json --ticker NVDA
"""

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

# Project root
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILE = ROOT / "data" / "NVDA.json"
DEFAULT_API_URL = os.environ.get("STREAMLIT_API_URL", "http://localhost:8000").rstrip("/")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load Glassdoor reviews from JSON file into the app for a company (by ticker)."
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_FILE,
        help=f"Path to JSON file (default: {DEFAULT_FILE})",
    )
    parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Ticker symbol (e.g. NVDA). Default: from file's 'ticker' key if present, else NVDA.",
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default=DEFAULT_API_URL,
        help=f"API base URL (default: {DEFAULT_API_URL})",
    )
    args = parser.parse_args()

    path = args.file if args.file.is_absolute() else ROOT / args.file
    if not path.exists():
        print(f"Error: File not found: {path}", file=sys.stderr)
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "reviews" in data:
        reviews = data["reviews"]
        ticker_from_file = data.get("ticker")
    elif isinstance(data, list):
        reviews = data
        ticker_from_file = None
    else:
        print("Error: JSON must be an object with 'reviews' key or an array of review objects.", file=sys.stderr)
        sys.exit(1)

    if not isinstance(reviews, list):
        print("Error: 'reviews' must be an array.", file=sys.stderr)
        sys.exit(1)

    ticker = (args.ticker or ticker_from_file or "NVDA").strip().upper()
    if not ticker:
        print("Error: Ticker is required (--ticker or 'ticker' key in file).", file=sys.stderr)
        sys.exit(1)

    api_url = args.api_url.rstrip("/")
    with httpx.Client(base_url=api_url, timeout=60.0) as client:
        r = client.get("/api/v1/companies", params={"page": 1, "page_size": 100})
        r.raise_for_status()
        payload = r.json()
        items = payload.get("items") or []
        company = next((c for c in items if (c.get("ticker") or "").upper() == ticker), None)
        if not company:
            print(f"Error: No company found with ticker {ticker}. Add the company in the UI first.", file=sys.stderr)
            sys.exit(1)
        company_id = company["id"]

        r2 = client.put(
            f"/api/v1/companies/{company_id}/raw/glassdoor_reviews",
            json=reviews,
        )
        r2.raise_for_status()
        out = r2.json()

    print(f"Stored {out['stored']} Glassdoor reviews for {ticker} (company_id={out['company_id']}).")
    print(out["message"])


if __name__ == "__main__":
    main()
