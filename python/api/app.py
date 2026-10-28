from fastapi import FastAPI

app = FastAPI(title="UNO Q Smart Home API")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "application": "unoq-smart-home"
    }


@app.get("/api/devices")
def list_devices():
    return {
        "devices": []
    }