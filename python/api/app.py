import asyncio
import json
import os
import re
import sqlite3
import threading
from pathlib import Path

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

DB_PATH = Path(
    os.getenv("SMART_HOME_DB", "/app/data/smart_home.db")
)

devices = {}
devices_lock = threading.RLock()
connected_clients = set()
main_loop = None


def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(DB_PATH), timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                room TEXT NOT NULL,
                online INTEGER NOT NULL DEFAULT 0,
                state TEXT NOT NULL DEFAULT 'unknown'
            )
        """)

        count = db.execute(
            "SELECT COUNT(*) FROM devices"
        ).fetchone()[0]

        if count == 0:
            db.execute("""
                INSERT INTO devices
                    (id, name, type, room, online, state)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                "living-room-light",
                "Salon Lambası",
                "light",
                "living-room",
                0,
                "unknown",
            ))


def load_devices():
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM devices ORDER BY room, name"
        ).fetchall()

    with devices_lock:
        devices.clear()

        for row in rows:
            devices[row["id"]] = {
                "id": row["id"],
                "name": row["name"],
                "type": row["type"],
                "room": row["room"],
                "online": bool(row["online"]),
                "state": row["state"],
            }


def save_device(device):
    with get_db() as db:
        db.execute("""
            INSERT INTO devices
                (id, name, type, room, online, state)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                type = excluded.type,
                room = excluded.room,
                online = excluded.online,
                state = excluded.state
        """, (
            device["id"],
            device["name"],
            device["type"],
            device["room"],
            int(device["online"]),
            str(device["state"]),
        ))


def get_device_snapshot():
    with devices_lock:
        return [dict(device) for device in devices.values()]


async def broadcast_devices():
    payload = {
        "type": "devices",
        "devices": get_device_snapshot(),
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
    loop = main_loop

    if loop is None or loop.is_closed():
        return

    try:
        asyncio.run_coroutine_threadsafe(
            broadcast_devices(), loop
        )
    except RuntimeError as exc:
        print(f"WebSocket broadcast error: {exc}")


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse("/app/python/api/static/index.html")


MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

mqtt_client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id="uno-q-smart-home-api",
)

if MQTT_USERNAME and MQTT_PASSWORD:
    mqtt_client.username_pw_set(
        MQTT_USERNAME,
        MQTT_PASSWORD,
    )


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
                device["online"] = (
                    payload.strip().lower() == "online"
                )

            # MQTT updates must not change the database identity.
            device["id"] = device_id
            device["room"] = room
            snapshot = dict(device)

        save_device(snapshot)
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

    init_db()
    load_devices()
    print(f"Device database ready: {DB_PATH}")

    try:
        mqtt_client.connect(
            MQTT_HOST, MQTT_PORT, keepalive=60
        )
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
            "devices": get_device_snapshot(),
        })

        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass
    finally:
        connected_clients.discard(websocket)


class DeviceCommand(BaseModel):
    state: str


class DeviceCreate(BaseModel):
    id: str
    name: str
    type: str
    room: str


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "application": "unoq-smart-home",
        "mqtt": mqtt_client.is_connected(),
        "websocket": (
            main_loop is not None and not main_loop.is_closed()
        ),
        "database": DB_PATH.exists(),
    }


@app.get("/api/devices")
def list_devices():
    return {"devices": get_device_snapshot()}


@app.post("/api/devices", status_code=201)
async def create_device(device: DeviceCreate):
    device_id = device.id.strip().lower()
    name = device.name.strip()
    device_type = device.type.strip().lower()
    room = device.room.strip().lower()

    slug_pattern = r"[a-z0-9]+(?:-[a-z0-9]+)*"

    if not re.fullmatch(slug_pattern, device_id):
        raise HTTPException(
            status_code=400,
            detail="Cihaz kimliği küçük harf, rakam ve tire içermelidir.",
        )

    if not re.fullmatch(slug_pattern, room):
        raise HTTPException(
            status_code=400,
            detail="Oda kimliği küçük harf, rakam ve tire içermelidir.",
        )

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Cihaz adı boş olamaz.",
        )

    allowed_types = {
        "light", "switch", "sensor", "thermostat", "unknown"
    }

    if device_type not in allowed_types:
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

    with devices_lock:
        if device_id in devices:
            raise HTTPException(
                status_code=409,
                detail="Bu cihaz kimliği zaten kayıtlı.",
            )

        try:
            save_device(new_device)
        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=409,
                detail="Bu cihaz kimliği zaten kayıtlı.",
            )
        devices[device_id] = new_device

    await broadcast_devices()

    return {
        "status": "created",
        "device": new_device,
    }


@app.delete("/api/devices/{device_id}")
async def delete_device(device_id: str):
    with devices_lock:
        if device_id not in devices:
            raise HTTPException(
                status_code=404,
                detail="Device not found",
            )

        with get_db() as db:
            db.execute(
                "DELETE FROM devices WHERE id = ?",
                (device_id,),
            )

        del devices[device_id]

    await broadcast_devices()

    return {
        "status": "deleted",
        "device_id": device_id,
    }


@app.post("/api/devices/{device_id}/command")
def command_device(device_id: str, command: DeviceCommand):
    if command.state not in ("ON", "OFF"):
        raise HTTPException(
            status_code=400,
            detail="state must be ON or OFF",
        )

    with devices_lock:
        device = devices.get(device_id)

        if device is None:
            raise HTTPException(
                status_code=404,
                detail="Device not found",
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
        raise HTTPException(
            status_code=502,
            detail="MQTT publish failed",
        )

    return {
        "status": "sent",
        "device_id": device_id,
        "command": command.state,
        "topic": topic,
    }
