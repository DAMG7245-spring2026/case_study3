"""Target company tickers and display labels (fallback only). Prefer get_company_options() from API."""
TARGET_TICKERS = [
    "CAT", "DE", "UNH", "HCA", "ADP", "PAYX", "WMT", "TGT", "JPM", "GS",
]
TARGET_TICKER_LABELS = {
    "CAT": "Caterpillar Inc.",
    "DE": "Deere & Company",
    "UNH": "UnitedHealth Group",
    "HCA": "HCA Healthcare",
    "ADP": "Automatic Data Processing",
    "PAYX": "Paychex Inc.",
    "WMT": "Walmart Inc.",
    "TGT": "Target Corporation",
    "JPM": "JPMorgan Chase",
    "GS": "Goldman Sachs",
}


def ticker_label(ticker: str) -> str:
    """Return 'TICKER - Name' for display."""
    return f"{ticker} — {TARGET_TICKER_LABELS.get(ticker, ticker)}"
