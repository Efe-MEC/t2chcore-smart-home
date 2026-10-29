
import json
import logging

import paho.mqtt.client as mqtt

from api.core.config import (
    MQTT_HOST,
    MQTT_PASSWORD,
    MQTT_PORT,
    MQTT_USERNAME,
)
from api.services.device_service import (
    add_or_update_device,
    get_device,
    schedule_device_broadcast,
)


logger = logging.getLogger(__name__)

mqtt_client: mqtt.Client | None = None


def on_connect(
    client,
    userdata,
    flags,
    reason_code,
    properties,
) -> None:
    """Subscribe to device topics after a successful MQTT connection."""
    if reason_code.is_failure:
        logger.error("MQTT connection failed: %s", reason_code)
        return

    logger.info("MQTT connected to %s:%s", MQTT_HOST, MQTT_PORT)

    client.subscribe("home/+/+/state")
    client.subscribe("home/+/+/availability")


def on_message(client, userdata, msg) -> None:
    """Update device state from an incoming MQTT message."""
    try:
        payload = msg.payload.decode("utf-8").strip()
        parts = msg.topic.split("/")

        if len(parts) != 4 or parts[0] != "home":
            logger.warning("Ignoring unexpected MQTT topic: %s", msg.topic)
            return

        _, room, device_id, message_type = parts

        if message_type not in {"state", "availability"}:
            return

        # Reuse existing metadata instead of replacing a registered device
        # with MQTT-generated defaults.
        device = get_device(device_id)

        if device is None:
            device = {
                "id": device_id,
                "name": device_id.replace("-", " ").title(),
                "type": "unknown",
                "room": room,
                "online": False,
                "state": "unknown",
            }

        if message_type == "state":
            try:
                state_data = json.loads(payload)
            except json.JSONDecodeError:
                state_data = payload

            if isinstance(state_data, dict):
                # Preserve the previous behavior for a {"state": ...}
                # payload while keeping other JSON sensor data available.
                if "state" in state_data:
                    state_value = state_data["state"]
                else:
                    state_value = state_data

            else:
                state_value = state_data

            device["state"] = (
                state_value
                if isinstance(state_value, str)
                else json.dumps(state_value, ensure_ascii=False)
            )

        elif message_type == "availability":
            device["online"] = payload.lower() == "online"

        # Topic identity is authoritative for ID and room.
        device["id"] = device_id
        device["room"] = room

        add_or_update_device(device)

        logger.info(
            "Device update: id=%s, message_type=%s",
            device_id,
            message_type,
        )

        schedule_device_broadcast()

    except (UnicodeDecodeError, ValueError, TypeError, KeyError):
        logger.exception("Failed to process MQTT message: %s", msg.topic)


def connect_mqtt() -> None:
    """Create the MQTT client and start its network loop."""
    global mqtt_client

    if mqtt_client is not None:
        logger.warning("MQTT client has already been initialized")
        return

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="uno-q-smart-home-api",
    )

    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    client.on_connect = on_connect
    client.on_message = on_message

    mqtt_client = client

    try:
        client.connect(
            MQTT_HOST,
            MQTT_PORT,
            keepalive=60,
        )
        client.loop_start()

    except Exception:
        mqtt_client = None
        logger.exception("Could not connect to MQTT broker")
        raise


def disconnect_mqtt() -> None:
    """Stop the MQTT network loop and disconnect cleanly."""
    global mqtt_client

    client = mqtt_client
    mqtt_client = None

    if client is None:
        return

    try:
        if client.is_connected():
            client.disconnect()

        client.loop_stop()
        logger.info("MQTT disconnected")

    except Exception:
        logger.exception("Error while disconnecting from MQTT broker")


def is_mqtt_connected() -> bool:
    """Return whether the MQTT client is connected."""
    client = mqtt_client
    return client is not None and client.is_connected()


def publish_device_command(
    room: str,
    device_id: str,
    state: str,
) -> dict:
    """Publish an ON/OFF command to a device."""
    client = mqtt_client

    if client is None or not client.is_connected():
        raise RuntimeError("MQTT broker is unavailable")

    topic = f"home/{room}/{device_id}/set"
    payload = json.dumps({"state": state})

    result = client.publish(
        topic,
        payload,
        qos=1,
    )

    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        raise RuntimeError("MQTT publish failed")

    return {
        "topic": topic,
        "payload": payload,
    }
