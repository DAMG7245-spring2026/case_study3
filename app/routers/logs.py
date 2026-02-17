"""API endpoint for backend log buffer (UI)."""
from fastapi import APIRouter

from app.log_buffer import get_log_lines

router = APIRouter(prefix="/api/v1", tags=["logs"])


@router.get("/logs")
async def get_logs():
    """Return recent backend log lines for the UI (scrollable view)."""
    lines = get_log_lines()
    return {"lines": lines, "total": len(lines)}
