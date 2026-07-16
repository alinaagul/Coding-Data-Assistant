from fastapi import APIRouter

from ..db_connection import connection_manager, model_provider

router = APIRouter(prefix="/api/connection", tags=["connection"])


@router.get("/status")
def status():
    """Read-only status: DB connection (configured via backend/.env) + local AI model."""
    return {
        "connected": connection_manager.is_connected,
        "connection": connection_manager.info.safe_dict() if connection_manager.info else None,
        "ai_model": model_provider.status(),
    }
