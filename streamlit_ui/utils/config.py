"""Streamlit UI configuration."""
import os


def get_api_url() -> str:
    """API base URL (no trailing slash). Default: deployed backend."""
    return os.environ.get("STREAMLIT_API_URL", "http://localhost:8000").rstrip("/")


def get_api_timeout() -> float:
    """Request timeout in seconds. Hosted backend can be slow; default 60s."""
    try:
        return float(os.environ.get("STREAMLIT_API_TIMEOUT", "60"))
    except ValueError:
        return 60.0
