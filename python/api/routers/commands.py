
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.services.device_service import get_device
from api.services.mqtt_service import publish_device_command


router = APIRouter(prefix="/api/devices", tags=["Commands"])


class DeviceCommand(BaseModel):
    state: str


@router.post("/{device_id}/command")
def send_device_command(
    device_id: str,
    command: DeviceCommand,
) -> dict:
    """Send an ON/OFF command to a device over MQTT."""
    requested_state = command.state.strip().upper()

    if requested_state not in {"ON", "OFF"}:
        raise HTTPException(
            status_code=400,
            detail="state must be ON or OFF",
        )

    device = get_device(device_id)

    if device is None:
        raise HTTPException(
            status_code=404,
            detail="Device not found",
        )

    try:
        published = publish_device_command(
            room=device["room"],
            device_id=device_id,
            state=requested_state,
        )
    except RuntimeError as exc:
        error_message = str(exc)

        if error_message == "MQTT broker is unavailable":
            raise HTTPException(
                status_code=503,
                detail=error_message,
            ) from exc

        raise HTTPException(
            status_code=502,
            detail=error_message,
        ) from exc

    return {
        "status": "sent",
        "device_id": device_id,
        "command": requested_state,
        "topic": published["topic"],
    }
