from threading import Thread

import uvicorn
from arduino.app_utils import App

from api.app import app


def start_web_server():
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info",
    )


if __name__ == "__main__":
    Thread(
        target=start_web_server,
        daemon=True,
    ).start()

    App.run()