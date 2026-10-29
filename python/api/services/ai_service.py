
import json
import logging
import urllib.error
import urllib.request

from api.core.config import AI_BASE_URL
from api.services.device_service import get_device_snapshot


logger = logging.getLogger(__name__)

AI_TIMEOUT_SECONDS = 120
AI_HEALTH_TIMEOUT_SECONDS = 5


SYSTEM_PROMPT = """
Sen UNO Q üzerinde çalışan, Türkçe yanıt veren yerel bir akıllı ev
danışmanısın.

Kurallar:
- Kullanıcıya kısa, açık ve güvenli Türkçe yanıtlar ver.
- Yalnızca sana sağlanan cihaz verilerini kullan.
- Gerçek sensör verisi veya cihaz durumu uydurma.
- Bilinmeyen değerleri açıkça "bilinmiyor" olarak belirt.
- Bu servis yalnızca danışmanlık ve soru-cevap içindir.
- MQTT komutu gönderme, araç çağırma veya cihaz kontrolü yapma.
- Kullanıcı cihaz kontrolü isterse dashboard üzerindeki kontrolleri
  kullanması gerektiğini açıkla.
- Cihaz listesi, uygulamanın mevcut anlık görüntüsüdür.
""".strip()


def check_ai_health() -> dict:
    """Check whether the local model server is reachable."""
    request = urllib.request.Request(
        f"{AI_BASE_URL}/health",
        headers={"Accept": "application/json"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=AI_HEALTH_TIMEOUT_SECONDS,
        ) as response:
            body = response.read().decode("utf-8")
            model_status = json.loads(body) if body else {}

        return {
            "status": "ok",
            "model_server": model_status,
        }

    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        json.JSONDecodeError,
    ) as exc:
        logger.warning("Local AI health check failed: %s", exc)
        raise RuntimeError(
            "Yerel yapay zekâ sunucusuna ulaşılamıyor."
        ) from exc


def chat_with_ai(
    message: str,
    history: list[dict[str, str]] | None = None,
) -> dict:
    """Generate a smart-home answer using the local model."""
    clean_message = message.strip()

    if not clean_message:
        raise ValueError("Mesaj boş olamaz.")

    device_context = json.dumps(
        get_device_snapshot(),
        ensure_ascii=False,
        separators=(",", ":"),
    )

    system_prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Mevcut cihaz verileri (JSON): {device_context}"
    )

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        }
    ]

    # Accept only valid user/assistant messages from the supplied history.
    for item in (history or [])[-10:]:
        role = item.get("role")
        content = item.get("content", "")

        if role not in {"user", "assistant"}:
            continue

        if not isinstance(content, str):
            continue

        content = content.strip()

        if content and len(content) <= 2000:
            messages.append(
                {
                    "role": role,
                    "content": content,
                }
            )

    messages.append(
        {
            "role": "user",
            "content": clean_message,
        }
    )

    payload = json.dumps(
        {
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 120,
            "stream": False,
        },
        ensure_ascii=False,
    ).encode("utf-8")

    request = urllib.request.Request(
        f"{AI_BASE_URL}/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=AI_TIMEOUT_SECONDS,
        ) as response:
            result = json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as exc:
        logger.error("Local AI server returned HTTP %s", exc.code)
        raise RuntimeError(
            "Yapay zekâ sunucusu isteği işleyemedi."
        ) from exc

    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        json.JSONDecodeError,
    ) as exc:
        logger.exception("Local AI request failed")
        raise RuntimeError(
            "Yerel yapay zekâ yanıt üretemedi."
        ) from exc

    try:
        answer = result["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, AttributeError, TypeError) as exc:
        logger.error("Unexpected response format from local AI server")
        raise RuntimeError(
            "Yapay zekâ sunucusundan geçersiz yanıt alındı."
        ) from exc

    if not answer:
        raise RuntimeError("Yapay zekâ boş yanıt döndürdü.")

    return {
        "answer": answer,
        "model": result.get("model", "local-model"),
    }
