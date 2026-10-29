
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.core.config import APP_TITLE, STATIC_DIR
from api.core.database import init_db
from api.routers import ai, commands, devices, health
from api.services import device_service, mqtt_service


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize application services and clean them up on shutdown."""
    device_service.main_loop = asyncio.get_running_loop()

    init_db()
    device_service.initialize_devices()
    logger.info("Device database initialized")

    try:
        mqtt_service.connect_mqtt()
    except Exception:
        # The API can still serve requests while MQTT is unavailable.
        logger.exception("MQTT is unavailable; API will continue running")

    try:
        yield
    finally:
        mqtt_service.disconnect_mqtt()
        device_service.main_loop = None
        logger.info("Smart-home API stopped")


app = FastAPI(
    title=APP_TITLE,
    lifespan=lifespan,
)

static_path = Path(STATIC_DIR)

app.mount(
    "/static",
    StaticFiles(directory=str(static_path)),
    name="static",
)


@app.get("/", include_in_schema=False)
def dashboard():
    """Serve the smart-home dashboard."""
    index_path = static_path / "index.html"

    if not index_path.is_file():
        logger.error("Dashboard file not found: %s", index_path)
        from fastapi import HTTPException

        raise HTTPException(
            status_code=500,
            detail="Dashboard file is unavailable.",
        )

    return FileResponse(index_path)


app.include_router(health.router)
app.include_router(devices.router)
app.include_router(commands.router)
app.include_router(ai.router)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Send device updates to connected dashboard clients."""
    await device_service.register_websocket(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await device_service.unregister_websocket(websocket)
