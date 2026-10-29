
import re
import sqlite3

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from api.core.database import delete_device as delete_device_from_db
from api.core.database import save_device
from api.services.device_service import (
    add_or_update_device,
    devices,
    devices_lock,
    get_device_snapshot,
    remove_device,
    schedule_device_broadcast,
)


router = APIRouter(prefix="/api/devices", tags=["Devices"])

ALLOWED_DEVICE_TYPES = {
    "light",
    "switch",
    "sensor",
    "thermostat",
    "unknown",
}

SLUG_PATTERN = r"[a-z0-9]+(?:-[a-z0-9]+)*"


class DeviceCreate(BaseModel):
    id: str
    name: str
    type: str
    room: str


@router.get("")
def list_devices() -> dict:
    """Return all registered devices."""
    return {
        "devices": get_device_snapshot(),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_device(payload: DeviceCreate) -> dict:
    """Validate and register a new device."""
    device_id = payload.id.strip().lower()
    name = payload.name.strip()
    device_type = payload.type.strip().lower()
    room = payload.room.strip().lower()

    if not re.fullmatch(SLUG_PATTERN, device_id):
        raise HTTPException(
            status_code=400,
            detail="Cihaz kimliği küçük harf, rakam ve tire içermelidir.",
        )

    if not re.fullmatch(SLUG_PATTERN, room):
        raise HTTPException(
            status_code=400,
            detail="Oda kimliği küçük harf, rakam ve tire içermelidir.",
        )

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Cihaz adı boş olamaz.",
        )

    if device_type not in ALLOWED_DEVICE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Desteklenmeyen cihaz türü.",
        )

    new_device = {
        "id": device_id,
        "name": name,
        "type": device_type,
        "room": room,
        "online": False,
        "state": "unknown",
    }

    # Check and persist under the same lock to avoid duplicate registrations.
    with devices_lock:
        if device_id in devices:
            raise HTTPException(
                status_code=409,
                detail="Bu cihaz kimliği zaten kayıtlı.",
            )

        try:
            save_device(new_device)
        except sqlite3.IntegrityError as exc:
            raise HTTPException(
                status_code=409,
                detail="Bu cihaz kimliği zaten kayıtlı.",
            ) from exc

        devices[device_id] = new_device.copy()

    schedule_device_broadcast()

    return {
        "status": "created",
        "device": new_device,
    }


@router.delete("/{device_id}")
def delete_device(device_id: str) -> dict:
    """Delete a device from the database and in-memory registry."""
    with devices_lock:
        if device_id not in devices:
            raise HTTPException(
                status_code=404,
                detail="Device not found",
            )

        deleted = delete_device_from_db(device_id)

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="Device not found",
            )

        remove_device(device_id)

    schedule_device_broadcast()

    return {
        "status": "deleted",
        "device_id": device_id,
    }
