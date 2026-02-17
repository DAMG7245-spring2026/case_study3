"""Industries list endpoint."""
from fastapi import APIRouter
from app.services import get_snowflake_service

router = APIRouter(prefix="/api/v1", tags=["Industries"])


@router.get("/industries")
async def list_industries():
    """List all industries (id, name, sector) for dropdowns."""
    db = get_snowflake_service()
    rows = db.execute_query(
        "SELECT id, name, sector FROM industries ORDER BY name"
    )
    return [
        {"id": str(row["id"]), "name": row["name"], "sector": row["sector"]}
        for row in (rows or [])
    ]
