
from pathlib import Path

from fastapi import APIRouter, HTTPException

from api.core.config import DB_PATH
from api.services import device_service
from api.services.ai_service import check_ai_health
from api.services.mqtt_service import is_mqtt_connected

router = APIRouter(tags=["Health"])


@router.get("/api/health")
def health_check():
    loop = device_service.main_loop

    return {
        "status": "ok",
        "application": "unoq-smart-home",
        "mqtt": is_mqtt_connected(),
        "websocket": loop is not None and not loop.is_closed(),
        "database": Path(DB_PATH).exists(),
    }


@router.get("/api/ai/health")
def ai_health_check():
    try:
        return check_ai_health()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc
