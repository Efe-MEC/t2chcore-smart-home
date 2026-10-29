
import os

from dotenv import load_dotenv


# Load environment variables without exposing secrets.
load_dotenv("/app/.env")


# Application
APP_TITLE = "UNO Q Smart Home API"


# Paths
STATIC_DIR = os.getenv(
    "STATIC_DIR",
    "/app/python/api/static",
)

DB_PATH = os.getenv(
    "SMART_HOME_DB",
    "/app/data/smart_home.db",
)


# MQTT configuration
MQTT_HOST = os.getenv(
    "MQTT_HOST",
    "127.0.0.1",
)

MQTT_PORT = int(
    os.getenv("MQTT_PORT", "1883")
)

MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")


# Local AI server configuration
AI_BASE_URL = os.getenv(
    "AI_BASE_URL",
    "http://llama-server:8081",
).rstrip("/")
