
import asyncio
import threading

from fastapi import WebSocket, WebSocketDisconnect

from api.core.database import load_devices, save_device


devices: dict[str, dict] = {}
devices_lock = threading.RLock()
connected_clients: set[WebSocket] = set()

main_loop: asyncio.AbstractEventLoop | None = None


def initialize_devices() -> None:
    """Load persisted devices into memory."""
    loaded_devices = load_devices()

    with devices_lock:
        devices.clear()
        devices.update(loaded_devices)


def get_device_snapshot() -> list[dict]:
    """Return a thread-safe list snapshot of all devices."""
    with devices_lock:
        return [
            device.copy()
            for device in devices.values()
        ]


def get_device(device_id: str) -> dict | None:
    """Return a copy of a device, or None if it does not exist."""
    with devices_lock:
        device = devices.get(device_id)
        return device.copy() if device is not None else None


def add_or_update_device(device: dict) -> dict:
    """Persist a device and update its in-memory representation."""
    saved_device = device.copy()
    saved_device["online"] = bool(saved_device["online"])

    with devices_lock:
        current_device = devices.get(saved_device["id"])

        # Preserve registered metadata when MQTT only reports state.
        if current_device is not None:
            saved_device["name"] = current_device["name"]
            saved_device["type"] = current_device["type"]

        save_device(saved_device)
        devices[saved_device["id"]] = saved_device.copy()

    return saved_device.copy()


def remove_device(device_id: str) -> bool:
    """Remove a device from the in-memory registry."""
    with devices_lock:
        if device_id not in devices:
            return False

        del devices[device_id]
        return True


async def register_websocket(websocket: WebSocket) -> None:
    """Accept a WebSocket client and send the initial device snapshot."""
    await websocket.accept()

    with devices_lock:
        connected_clients.add(websocket)

    try:
        await websocket.send_json(
            {
                "type": "devices",
                "devices": get_device_snapshot(),
            }
        )
    except (WebSocketDisconnect, RuntimeError, OSError):
        await unregister_websocket(websocket)
        raise


async def unregister_websocket(websocket: WebSocket) -> None:
    """Remove a disconnected WebSocket client."""
    with devices_lock:
        connected_clients.discard(websocket)


async def broadcast_devices() -> None:
    """Broadcast the latest device list to all connected clients."""
    payload = {
        "type": "devices",
        "devices": get_device_snapshot(),
    }

    with devices_lock:
        clients = list(connected_clients)

    disconnected = []

    for websocket in clients:
        try:
            await websocket.send_json(payload)
        except (WebSocketDisconnect, RuntimeError, OSError):
            disconnected.append(websocket)

    if disconnected:
        with devices_lock:
            for websocket in disconnected:
                connected_clients.discard(websocket)


def schedule_device_broadcast() -> None:
    """Schedule a broadcast from an MQTT worker thread."""
    loop = main_loop

    if loop is None or loop.is_closed():
        return

    try:
        asyncio.run_coroutine_threadsafe(
            broadcast_devices(),
            loop,
        )
    except RuntimeError:
        # The application event loop may be shutting down.
        pass
