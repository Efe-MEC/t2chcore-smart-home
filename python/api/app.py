
import json
import os
import threading

import paho.mqtt.client as mqtt
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv("/app/.env")

app = FastAPI(title="UNO Q Smart Home API")

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

        if device_id not in devices:
            devices[device_id] = {
                "id": device_id,
                "name": device_id,
                "type": "unknown",
                "room": room,
                "online": False,
                "state": "unknown",
            }

        if message_type == "state":
            try:
                state = json.loads(payload)
            except json.JSONDecodeError:
                state = {"state": payload}

            devices[device_id].update(state)

        elif message_type == "availability":
            devices[device_id]["online"] = payload.lower() == "online"

    except Exception as exc:
        print(f"MQTT message error: {exc}")


mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message


@app.on_event("startup")
def startup():
    try:
        mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        mqtt_client.loop_start()
    except Exception as exc:
        print(f"MQTT unavailable: {exc}")


@app.on_event("shutdown")
def shutdown():
    mqtt_client.loop_stop()
    mqtt_client.disconnect()


class DeviceCommand(BaseModel):
    state: str


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "application": "unoq-smart-home",
        "mqtt": mqtt_client.is_connected(),
    }


@app.get("/api/devices")
def list_devices():
    return {"devices": list(devices.values())}


@app.post("/api/devices/{device_id}/command")
def command_device(device_id: str, command: DeviceCommand):
    if device_id not in devices:
        raise HTTPException(status_code=404, detail="Device not found")

    if command.state not in ("ON", "OFF"):
        raise HTTPException(
            status_code=400,
            detail="state must be ON or OFF",
        )

    if not mqtt_client.is_connected():
        raise HTTPException(
            status_code=503,
            detail="MQTT broker is unavailable",
        )

    room = devices[device_id]["room"]
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
