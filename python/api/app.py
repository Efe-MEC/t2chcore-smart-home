import asyncio
import json
import os
import threading

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv("/app/.env")

app = FastAPI(title="UNO Q Smart Home API")

app.mount(
    "/static",
    StaticFiles(directory="/app/python/api/static"),
    name="static",
)


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse("/app/python/api/static/index.html")


MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

devices = {
    "living-room-light": {
        "id": "living-room-light",
        "name": "Salon Lambası",
        "type": "light",
        "room": "living-room",
        "online": False,
        "state": "unknown",
    }
}

connected_clients = set()
main_loop = None
devices_lock = threading.Lock()

mqtt_client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id="uno-q-smart-home-api",
)

if MQTT_USERNAME and MQTT_PASSWORD:
    mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)


async def broadcast_devices():
    """Send the current device list to every connected dashboard."""
    with devices_lock:
        payload = {
            "type": "devices",
            "devices": [dict(device) for device in devices.values()],
        }

    disconnected = []

    for websocket in list(connected_clients):
        try:
            await websocket.send_json(payload)
        except (WebSocketDisconnect, RuntimeError, OSError):
            disconnected.append(websocket)

    for websocket in disconnected:
        connected_clients.discard(websocket)


def schedule_device_broadcast():
    """Schedule a dashboard update from the MQTT background thread."""
    loop = main_loop

    if loop is None or loop.is_closed():
        return

    try:
        asyncio.run_coroutine_threadsafe(broadcast_devices(), loop)
    except RuntimeError as exc:
        print(f"WebSocket broadcast scheduling error: {exc}")


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("MQTT connected")
        client.subscribe("home/+/+/state")
        client.subscribe("home/+/+/availability")
    else:
        print(f"MQTT connection failed: {reason_code}")


def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        parts = msg.topic.split("/")

        if len(parts) != 4 or parts[0] != "home":
            return

        room, device_id, message_type = parts[1], parts[2], parts[3]

        if message_type not in ("state", "availability"):
            return

        with devices_lock:
            if device_id not in devices:
                devices[device_id] = {
                    "id": device_id,
                    "name": device_id,
                    "type": "unknown",
                    "room": room,
                    "online": False,
                    "state": "unknown",
                }

            device = devices[device_id]

            if message_type == "state":
                try:
                    state_data = json.loads(payload)
                except json.JSONDecodeError:
                    state_data = {"state": payload}

                if isinstance(state_data, dict):
                    device.update(state_data)
                else:
                    device["state"] = state_data

            elif message_type == "availability":
                device["online"] = payload.strip().lower() == "online"

        print(f"Device update: {device_id} ({message_type})")
        schedule_device_broadcast()

    except Exception as exc:
        print(f"MQTT message error: {exc}")


mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message


@app.on_event("startup")
async def startup():
    global main_loop

    main_loop = asyncio.get_running_loop()

    try:
        mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        mqtt_client.loop_start()
    except Exception as exc:
        print(f"MQTT unavailable: {exc}")


@app.on_event("shutdown")
def shutdown():
    mqtt_client.loop_stop()
    mqtt_client.disconnect()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)

    try:
        await websocket.send_json({
            "type": "devices",
            "devices": list(devices.values()),
        })

        # Keep the connection open until the browser disconnects.
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass

    finally:
        connected_clients.discard(websocket)


class DeviceCommand(BaseModel):
    state: str


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "application": "unoq-smart-home",
        "mqtt": mqtt_client.is_connected(),
        "websocket": main_loop is not None and not main_loop.is_closed(),
    }


@app.get("/api/devices")
def list_devices():
    with devices_lock:
        return {"devices": [dict(device) for device in devices.values()]}


@app.post("/api/devices/{device_id}/command")
def command_device(device_id: str, command: DeviceCommand):
    with devices_lock:
        device = devices.get(device_id)

        if device is None:
            raise HTTPException(status_code=404, detail="Device not found")

        if command.state not in ("ON", "OFF"):
            raise HTTPException(
                status_code=400,
                detail="state must be ON or OFF",
            )

        room = device["room"]

    if not mqtt_client.is_connected():
        raise HTTPException(
            status_code=503,
            detail="MQTT broker is unavailable",
        )

    topic = f"home/{room}/{device_id}/set"
    result = mqtt_client.publish(
        topic,
        json.dumps({"state": command.state}),
        qos=1,
    )

    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        raise HTTPException(status_code=502, detail="MQTT publish failed")

    return {
        "status": "sent",
        "device_id": device_id,
        "command": command.state,
        "topic": topic,
    }
