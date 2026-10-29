
import re
import unicodedata

from api.services.device_service import get_device_snapshot
from api.services.mqtt_service import publish_device_command


TYPE_ALIASES = {
    "light": (
        "isik",
        "isig",
        "lamba",
        "lambasi",
        "aydinlatma",
        "light",
    ),
    "switch": (
        "anahtar",
        "dugme",
        "switch",
        "priz",
    ),
    "sensor": (
        "sensor",
        "sicaklik sensoru",
        "hareket sensoru",
    ),
    "thermostat": (
        "termostat",
        "sicaklik ayari",
    ),
}

ROOM_ALIASES = {
    "living-room": ("salon", "oturma odasi", "living room"),
    "bedroom": ("yatak odasi", "bedroom"),
    "kitchen": ("mutfak", "kitchen"),
    "bathroom": ("banyo", "bathroom"),
    "hallway": ("koridor", "hol", "hallway"),
    "office": ("ofis", "office", "calisma odasi"),
}

ON_PATTERNS = (
    r"\bacabilir misin\b",
    r"\bacar misin\b",
    r"\bac\b",
    r"\byakabilir misin\b",
    r"\byakar misin\b",
    r"\byak\b",
    r"\bcalistir\b",
    r"\bdevreye al\b",
)

OFF_PATTERNS = (
    r"\bkapatabilir misin\b",
    r"\bkapatir misin\b",
    r"\bkapat\b",
    r"\bsondurebilir misin\b",
    r"\bsondurur musun\b",
    r"\bsondur\b",
    r"\bdevreden cikar\b",
)

EXPLANATION_PREFIXES = (
    "nasil ",
    "neden ",
    "ne zaman ",
    "ne demek",
    "acikla ",
    "anlat ",
    "aciklar misin ",
)

ROOM_WORDS = {
    "salon", "oturma", "odasi", "living", "room",
    "yatak", "bedroom", "mutfak", "kitchen",
    "banyo", "bathroom", "koridor", "hallway",
    "hol", "ofis", "office", "calisma",
}

GENERIC_DEVICE_WORDS = {
    "isik", "isig", "lamba", "lambasi", "aydinlatma",
    "light", "anahtar", "dugme", "switch", "priz",
    "sensor", "termostat",
}


def normalize_text(value: str) -> str:
    """Normalize Turkish text for predictable matching."""
    value = value.lower().replace("ı", "i")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(
        char
        for char in value
        if not unicodedata.combining(char)
    )
    value = re.sub(r"[^a-z0-9\s-]", " ", value)
    value = value.replace("-", " ")
    return " ".join(value.split())


def detect_action(message: str) -> str | None:
    """Recognize explicit ON/OFF requests."""
    for prefix in EXPLANATION_PREFIXES:
        if message.startswith(prefix):
            return None

    for pattern in ON_PATTERNS:
        if re.search(pattern, message):
            return "ON"

    for pattern in OFF_PATTERNS:
        if re.search(pattern, message):
            return "OFF"

    return None


def mentions_alias(
    text: str,
    aliases: tuple[str, ...],
) -> bool:
    """Match a normalized phrase or word prefix."""
    for alias in aliases:
        normalized_alias = normalize_text(alias)

        if not normalized_alias:
            continue

        if " " in normalized_alias:
            if normalized_alias in text:
                return True
        elif re.search(
            rf"\b{re.escape(normalized_alias)}\w*\b",
            text,
        ):
            return True

    return False


def aliases_for_room(room: str) -> tuple[str, ...]:
    normalized_room = normalize_text(room)
    room_key = normalized_room.replace(" ", "-")

    aliases = list(ROOM_ALIASES.get(room_key, ()))
    if normalized_room:
        aliases.append(normalized_room)

    return tuple(aliases)


def mentioned_rooms(text: str) -> set[str]:
    """Find room names independently of registered devices."""
    result = set()

    for room_key, aliases in ROOM_ALIASES.items():
        if mentions_alias(text, aliases):
            result.add(room_key)

    return result


def device_type_mentioned(
    text: str,
    device_type: str,
) -> bool:
    return mentions_alias(
        text,
        TYPE_ALIASES.get(device_type, ()),
    )


def device_name_mentioned(
    text: str,
    device: dict,
) -> bool:
    """Match the registered name or a distinctive name/ID token."""
    name = normalize_text(str(device.get("name", "")))

    if name and name in text:
        return True

    device_id = normalize_text(str(device.get("id", "")))
    distinctive_terms = set()

    for value in (name, device_id):
        for token in value.split():
            if (
                len(token) >= 4
                and token not in ROOM_WORDS
                and token not in GENERIC_DEVICE_WORDS
            ):
                distinctive_terms.add(token)

    return any(term in text for term in distinctive_terms)


def room_matches_device(
    text: str,
    device: dict,
    requested_rooms: set[str],
) -> bool:
    room = str(device.get("room", ""))
    normalized_room = normalize_text(room).replace(" ", "-")

    if requested_rooms:
        return normalized_room in requested_rooms

    return mentions_alias(text, aliases_for_room(room))


def make_response(
    answer: str,
    status: str,
    **extra,
) -> dict:
    return {
        "answer": answer,
        "model": "command-router",
        "action": "device_command",
        "command": {
            "status": status,
            **extra,
        },
    }


def handle_natural_language_command(
    message: str,
) -> dict | None:
    """
    Route explicit ON/OFF requests safely.

    Return None only when the message is not recognized as
    a device-control request.
    """
    text = normalize_text(message)
    state = detect_action(text)

    if state is None:
        return None

    devices = get_device_snapshot()
    requested_rooms = mentioned_rooms(text)

    name_matches = [
        device
        for device in devices
        if device_name_mentioned(text, device)
    ]

    type_matches = [
        device
        for device in devices
        if device_type_mentioned(
            text,
            str(device.get("type", "unknown")),
        )
    ]

    has_type_reference = any(
        device_type_mentioned(
            text,
            str(device.get("type", "unknown")),
        )
        for device in devices
    )

    # A recognized action without a target must not reach the LLM.
    if not name_matches and not has_type_reference and not requested_rooms:
        return make_response(
            "Hangi cihazı açmamı veya kapatmamı istiyorsun? "
            "Örneğin: Salon lambasını aç.",
            "needs_clarification",
        )

    # An explicitly named device takes precedence, unless the
    # user also specified a conflicting room.
    if name_matches:
        candidates = [
            device
            for device in name_matches
            if (
                not requested_rooms
                or room_matches_device(
                    text,
                    device,
                    requested_rooms,
                )
            )
        ]
    elif requested_rooms:
        # Never substitute a device from another room.
        candidates = [
            device
            for device in devices
            if (
                device_type_mentioned(
                    text,
                    str(device.get("type", "unknown")),
                )
                and room_matches_device(
                    text,
                    device,
                    requested_rooms,
                )
            )
        ]
    elif has_type_reference:
        candidates = type_matches
    else:
        candidates = []

    # Deduplicate by registered device ID.
    candidates_by_id = {
        str(device.get("id")): device
        for device in candidates
        if device.get("id")
    }
    candidates = list(candidates_by_id.values())

    if not candidates:
        return make_response(
            "Bu isteğe uygun kayıtlı bir cihaz bulamadım. "
            "Cihazın adını ve bulunduğu odayı kontrol et.",
            "device_not_found",
        )

    if len(candidates) > 1:
        names = ", ".join(
            str(device.get("name", device.get("id", "Bilinmeyen cihaz")))
            for device in candidates
        )
        return make_response(
            f"Birden fazla cihaz eşleşti: {names}. "
            "Lütfen kontrol etmek istediğin cihazı belirt.",
            "needs_clarification",
        )

    device = candidates[0]
    device_id = str(device.get("id", ""))
    device_name = str(device.get("name", device_id))
    device_type = str(device.get("type", "unknown"))

    if device_type not in {"light", "switch"}:
        return make_response(
            f"{device_name} için açma/kapatma kontrolü desteklenmiyor.",
            "unsupported_device",
            device_id=device_id,
        )

    # Fail closed: never send commands to offline/unverified devices.
    if device.get("online") is not True:
        return make_response(
            f"{device_name} şu anda çevrimdışı veya bağlantısı "
            "doğrulanmamış. Güvenlik nedeniyle komut göndermedim. "
            "Önce cihaz bağlantısını kontrol et.",
            "offline",
            device_id=device_id,
        )

    try:
        publish_device_command(
            room=str(device["room"]),
            device_id=device_id,
            state=state,
        )
    except RuntimeError:
        return make_response(
            f"{device_name} için MQTT komutu gönderilemedi. "
            "MQTT bağlantısını kontrol et.",
            "publish_failed",
            device_id=device_id,
        )

    action_text = "açma" if state == "ON" else "kapatma"

    return make_response(
        f"{device_name} için {action_text} komutu MQTT'ye gönderildi. "
        "Cihazdan durum geri bildirimi gelmeden fiziksel durum "
        "doğrulanmış sayılmaz.",
        "sent",
        device_id=device_id,
        state=state,
    )
