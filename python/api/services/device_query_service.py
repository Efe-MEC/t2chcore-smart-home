"""Deterministic Turkish responses for device connectivity questions."""

import unicodedata

from api.services.device_service import get_device_snapshot


def _normalize(text: str) -> str:
    """Normalize Turkish text for simple intent and device-name matching."""
    text = text.lower().translate(str.maketrans({"ı": "i"}))
    text = unicodedata.normalize("NFKD", text)
    return "".join(char for char in text if not unicodedata.combining(char))


def answer_device_query(message: str) -> dict | None:
    """Answer connectivity questions from the live device snapshot."""
    text = _normalize(message)

    status_terms = (
        "cevrimici",
        "cevrimdisi",
        "online",
        "offline",
        "bagli mi",
        "baglanti durumu",
        "baglantisi var mi",
        "hangi cihazlar",
        "cihazlarin durumu",
        "cihaz durumu",
    )

    if not any(term in text for term in status_terms):
        return None

    devices = get_device_snapshot()

    if not devices:
        return {
            "answer": "Henüz kayıtlı bir akıllı ev cihazı bulunmuyor.",
            "model": "device-status",
        }

    online_devices = [
        device for device in devices
        if device.get("online") is True
    ]
    offline_devices = [
        device for device in devices
        if device.get("online") is not True
    ]

    # If a particular device is mentioned, answer for that device.
    for device in devices:
        name = _normalize(str(device.get("name", "")))
        device_id = _normalize(str(device.get("id", "")))

        if (name and name in text) or (device_id and device_id in text):
            device_name = device.get("name", "Cihaz")

            if device.get("online") is True:
                answer = f"{device_name} şu anda çevrimiçi."
            else:
                answer = (
                    f"{device_name} şu anda çevrimdışı veya bağlantısı "
                    "doğrulanmamış."
                )

            return {"answer": answer, "model": "device-status"}

    if online_devices:
        names = ", ".join(
            str(device.get("name", "İsimsiz cihaz"))
            for device in online_devices
        )
        answer = f"Şu anda çevrimiçi olan cihazlar: {names}."
    else:
        answer = "Şu anda kayıtlı hiçbir cihaz çevrimiçi değil."

    if offline_devices:
        names = ", ".join(
            str(device.get("name", "İsimsiz cihaz"))
            for device in offline_devices
        )
        answer += f" Çevrimdışı veya bağlantısı doğrulanmamış cihazlar: {names}."

    return {"answer": answer, "model": "device-status"}
