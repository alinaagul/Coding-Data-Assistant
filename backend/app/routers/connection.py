from fastapi import APIRouter, HTTPException

from ..db_connection import connection_manager, model_provider, SqlServerConnectionInfo
from ..schemas import ConnectionPayload
from ..config import get_settings

router = APIRouter(prefix="/api/connection", tags=["connection"])
settings = get_settings()


def _to_info(payload: ConnectionPayload) -> SqlServerConnectionInfo:
    return SqlServerConnectionInfo(
        server=payload.server,
        port=payload.port,
        database=payload.database,
        username=payload.username,
        password=payload.password,
        driver=payload.driver or settings.mssql_driver,
        encrypt=payload.encrypt,
        trust_server_certificate=payload.trust_server_certificate,
    )


@router.post("/test")
def test_connection(payload: ConnectionPayload):
    """Verify credentials work WITHOUT saving them as the active connection."""
    result = connection_manager.test_connection(_to_info(payload))
    return result


@router.post("/connect")
def connect(payload: ConnectionPayload):
    """Test, then persist and activate this connection profile."""
    result = connection_manager.connect(_to_info(payload), persist=True)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Connection failed."))
    return result


@router.post("/disconnect")
def disconnect():
    connection_manager.disconnect()
    return {"success": True}


@router.get("/status")
def status():
    return {
        "connected": connection_manager.is_connected,
        "connection": connection_manager.info.safe_dict() if connection_manager.info else None,
        "ai_model": model_provider.status(),
    }
