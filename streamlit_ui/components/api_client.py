"""HTTP client for FastAPI evidence collection endpoints."""
from typing import Any, Optional
from uuid import UUID

import httpx

from streamlit_ui.utils.config import get_api_url, get_api_timeout


def get_client(base_url: Optional[str] = None) -> httpx.Client:
    """Return an httpx client with base URL. Timeout from config (default 60s for hosted backend)."""
    url = (base_url or get_api_url()).rstrip("/")
    return httpx.Client(base_url=url, timeout=get_api_timeout())


def get_evidence_stats(client: Optional[httpx.Client] = None) -> dict[str, Any]:
    """GET /api/v1/evidence/stats."""
    c = client or get_client()
    if not client:
        c = get_client()
    try:
        r = c.get("/api/v1/evidence/stats")
        r.raise_for_status()
        return r.json()
    finally:
        if not client:
            c.close()


def get_target_companies(client: Optional[httpx.Client] = None) -> dict[str, Any]:
    """GET /api/v1/target-companies."""
    c = client or get_client()
    try:
        r = c.get("/api/v1/target-companies")
        r.raise_for_status()
        return r.json()
    finally:
        if not client:
            c.close()


def get_companies(
    client: Optional[httpx.Client] = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    """GET /api/v1/companies (list with id, ticker, name for Evidence dropdown)."""
    c = client or get_client()
    try:
        r = c.get("/api/v1/companies", params={"page": page, "page_size": page_size})
        r.raise_for_status()
        return r.json()
    finally:
        if not client:
            c.close()


def get_industries(client: Optional[httpx.Client] = None) -> list[dict[str, Any]]:
    """GET /api/v1/industries. Returns list of { id, name, sector }."""
    c = client or get_client()
    try:
        r = c.get("/api/v1/industries")
        r.raise_for_status()
        return r.json()
    finally:
        if not client:
            c.close()


def get_company(company_id: str | UUID, client: Optional[httpx.Client] = None) -> dict[str, Any]:
    """GET /api/v1/companies/{company_id}."""
    c = client or get_client()
    try:
        r = c.get(f"/api/v1/companies/{company_id}")
        r.raise_for_status()
        return r.json()
    finally:
        if not client:
            c.close()


def create_company(
    name: str,
    ticker: str,
    industry_id: str,
    client: Optional[httpx.Client] = None,
    position_factor: float = 0.0,
    domain: Optional[str] = None,
    careers_url: Optional[str] = None,
    news_url: Optional[str] = None,
    leadership_url: Optional[str] = None,
) -> dict[str, Any]:
    """POST /api/v1/companies. Returns created company. Raises on 409 (duplicate ticker)."""
    c = client or get_client()
    body: dict[str, Any] = {
        "name": name,
        "ticker": (ticker or "").strip().upper(),
        "industry_id": industry_id,
        "position_factor": position_factor,
    }
    if domain is not None:
        body["domain"] = domain
    if careers_url is not None:
        body["careers_url"] = careers_url
    if news_url is not None:
        body["news_url"] = news_url
    if leadership_url is not None:
        body["leadership_url"] = leadership_url
    try:
        r = c.post("/api/v1/companies", json=body)
        r.raise_for_status()
        return r.json()
    finally:
        if not client:
            c.close()


def update_company(
    company_id: str | UUID,
    client: Optional[httpx.Client] = None,
    name: Optional[str] = None,
    ticker: Optional[str] = None,
    industry_id: Optional[str] = None,
    position_factor: Optional[float] = None,
    domain: Optional[str] = None,
    careers_url: Optional[str] = None,
    news_url: Optional[str] = None,
    leadership_url: Optional[str] = None,
) -> dict[str, Any]:
    """PUT /api/v1/companies/{company_id}. Only include fields to update."""
    c = client or get_client()
    body: dict[str, Any] = {}
    if name is not None:
        body["name"] = name
    if ticker is not None:
        body["ticker"] = ticker.strip().upper()
    if industry_id is not None:
        body["industry_id"] = industry_id
    if position_factor is not None:
        body["position_factor"] = position_factor
    if domain is not None:
        body["domain"] = domain
    if careers_url is not None:
        body["careers_url"] = careers_url
    if news_url is not None:
        body["news_url"] = news_url
    if leadership_url is not None:
        body["leadership_url"] = leadership_url
    try:
        r = c.put(f"/api/v1/companies/{company_id}", json=body)
        r.raise_for_status()
        return r.json()
    finally:
        if not client:
            c.close()


def delete_company(company_id: str | UUID, client: Optional[httpx.Client] = None) -> None:
    """DELETE /api/v1/companies/{company_id} (soft delete)."""
    c = client or get_client()
    try:
        r = c.delete(f"/api/v1/companies/{company_id}")
        r.raise_for_status()
    finally:
        if not client:
            c.close()


def get_ticker_to_company_id(client: Optional[httpx.Client] = None) -> dict[str, str]:
    """Build ticker -> company_id (UUID string) from GET /api/v1/companies. Used to resolve ticker to ID."""
    data = get_companies(client, page=1, page_size=100)
    items = data.get("items") or []
    return {str(c.get("ticker", "")): str(c["id"]) for c in items if c.get("id") and c.get("ticker")}


def get_company_options(client: Optional[httpx.Client] = None) -> tuple[list[str], dict[str, str]]:
    """Return (ticker list with '' first, ticker -> 'TICKER — Name' for format_func). From API."""
    data = get_companies(client, page=1, page_size=100)
    items = data.get("items") or []
    tickers = [str(c.get("ticker", "")) for c in items if c.get("ticker")]
    labels = {t: f"{t} — {c.get('name', t)}" for c in items for t in [str(c.get("ticker", ""))] if t}
    return ([""] + tickers, labels)


def get_documents(
    client: Optional[httpx.Client] = None,
    page: int = 1,
    page_size: int = 20,
    company_id: Optional[UUID] = None,
    ticker: Optional[str] = None,
    filing_type: Optional[str] = None,
    status: Optional[str] = None,
) -> dict[str, Any]:
    """GET /api/v1/documents with optional filters."""
    c = client or get_client()
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if company_id is not None:
        params["company_id"] = str(company_id)
    if ticker:
        params["ticker"] = ticker
    if filing_type:
        params["filing_type"] = filing_type
    if status:
        params["status"] = status
    try:
        r = c.get("/api/v1/documents", params=params)
        r.raise_for_status()
        return r.json()
    finally:
        if not client:
            c.close()


def get_document(document_id: UUID, client: Optional[httpx.Client] = None) -> dict[str, Any]:
    """GET /api/v1/documents/{document_id}."""
    c = client or get_client()
    try:
        r = c.get(f"/api/v1/documents/{document_id}")
        r.raise_for_status()
        return r.json()
    finally:
        if not client:
            c.close()


def get_document_chunks(
    document_id: UUID,
    client: Optional[httpx.Client] = None,
    page: int = 1,
    page_size: int = 20,
    section: Optional[str] = None,
) -> dict[str, Any]:
    """GET /api/v1/documents/{document_id}/chunks."""
    c = client or get_client()
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if section:
        params["section"] = section
    try:
        r = c.get(f"/api/v1/documents/{document_id}/chunks", params=params)
        r.raise_for_status()
        return r.json()
    finally:
        if not client:
            c.close()


def collect_documents(
    company_id: str | UUID,
    filing_types: list[str],
    years_back: int = 3,
    client: Optional[httpx.Client] = None,
) -> dict[str, Any]:
    """POST /api/v1/documents/collect. Triggers background document collection. Returns task_id, status, message."""
    c = client or get_client()
    body: dict[str, Any] = {
        "company_id": str(company_id),
        "filing_types": filing_types,
        "years_back": years_back,
    }
    try:
        r = c.post("/api/v1/documents/collect", json=body)
        r.raise_for_status()
        return r.json()
    finally:
        if not client:
            c.close()


def get_document_collection_logs(
    task_id: str,
    client: Optional[httpx.Client] = None,
) -> dict[str, Any]:
    """GET /api/v1/documents/collect/logs/{task_id}. Returns { task_id, logs: list[str], finished: bool }."""
    c = client or get_client()
    try:
        r = c.get(f"/api/v1/documents/collect/logs/{task_id}")
        r.raise_for_status()
        return r.json()
    finally:
        if not client:
            c.close()


def get_backend_logs(client: Optional[httpx.Client] = None) -> dict[str, Any]:
    """GET /api/v1/logs. Returns { lines: list[str], total: int }."""
    c = client or get_client()
    try:
        r = c.get("/api/v1/logs")
        r.raise_for_status()
        return r.json()
    finally:
        if not client:
            c.close()


def collect_signals(
    company_id: str | UUID,
    categories: list[str],
    client: Optional[httpx.Client] = None,
) -> dict[str, Any]:
    """POST /api/v1/signals/collect. Triggers background signal collection. Returns task_id, status, message."""
    c = client or get_client()
    body: dict[str, Any] = {
        "company_id": str(company_id),
        "categories": categories,
    }
    try:
        r = c.post("/api/v1/signals/collect", json=body)
        r.raise_for_status()
        return r.json()
    finally:
        if not client:
            c.close()


def get_signal_collection_logs(
    task_id: str,
    client: Optional[httpx.Client] = None,
) -> dict[str, Any]:
    """GET /api/v1/signals/collect/logs/{task_id}. Returns { task_id, logs: list[str], finished: bool }."""
    c = client or get_client()
    try:
        r = c.get(f"/api/v1/signals/collect/logs/{task_id}")
        r.raise_for_status()
        return r.json()
    finally:
        if not client:
            c.close()


def get_signal_formulas(client: Optional[httpx.Client] = None) -> dict[str, Any]:
    """GET /api/v1/signals/formulas. Returns { formulas: dict[str, str] }."""
    c = client or get_client()
    try:
        r = c.get("/api/v1/signals/formulas")
        r.raise_for_status()
        return r.json()
    finally:
        if not client:
            c.close()


def compute_signals(
    company_id: str | UUID,
    categories: Optional[list[str]] = None,
    client: Optional[httpx.Client] = None,
) -> dict[str, Any]:
    """POST /api/v1/signals/compute. Returns { computed: list[str], message: str }."""
    c = client or get_client()
    body: dict[str, Any] = {"company_id": str(company_id)}
    if categories is not None:
        body["categories"] = categories
    try:
        r = c.post("/api/v1/signals/compute", json=body)
        r.raise_for_status()
        return r.json()
    finally:
        if not client:
            c.close()


def get_signals(
    client: Optional[httpx.Client] = None,
    page: int = 1,
    page_size: int = 20,
    company_id: Optional[UUID] = None,
    category: Optional[str] = None,
) -> dict[str, Any]:
    """GET /api/v1/signals."""
    c = client or get_client()
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if company_id is not None:
        params["company_id"] = str(company_id)
    if category:
        params["category"] = category
    try:
        r = c.get("/api/v1/signals", params=params)
        r.raise_for_status()
        return r.json()
    finally:
        if not client:
            c.close()


def get_company_signal_summary(
    company_id: UUID, client: Optional[httpx.Client] = None
) -> Optional[dict[str, Any]]:
    """GET /api/v1/companies/{company_id}/signals."""
    c = client or get_client()
    try:
        r = c.get(f"/api/v1/companies/{company_id}/signals")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    finally:
        if not client:
            c.close()


def get_company_evidence(
    company_id: UUID, client: Optional[httpx.Client] = None
) -> dict[str, Any]:
    """GET /api/v1/companies/{company_id}/evidence."""
    c = client or get_client()
    try:
        r = c.get(f"/api/v1/companies/{company_id}/evidence")
        r.raise_for_status()
        return r.json()
    finally:
        if not client:
            c.close()


def post_backfill(
    tickers: Optional[list[str]] = None,
    include_documents: bool = True,
    include_signals: bool = True,
    years_back: int = 3,
    filing_types: Optional[list[str]] = None,
    client: Optional[httpx.Client] = None,
) -> dict[str, Any]:
    """POST /api/v1/evidence/backfill."""
    c = client or get_client()
    body: dict[str, Any] = {
        "include_documents": include_documents,
        "include_signals": include_signals,
        "years_back": years_back,
    }
    if tickers is not None:
        body["tickers"] = tickers
    if filing_types is not None:
        body["filing_types"] = filing_types
    try:
        r = c.post("/api/v1/evidence/backfill", json=body)
        r.raise_for_status()
        return r.json()
    finally:
        if not client:
            c.close()
