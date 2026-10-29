
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.services.ai_service import chat_with_ai


router = APIRouter(prefix="/api/ai", tags=["AI"])


class ChatMessage(BaseModel):
    role: str
    content: str


class AIChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatMessage] = Field(
        default_factory=list,
        max_length=10,
    )


@router.post("/chat")
def ai_chat(request: AIChatRequest) -> dict:
    """Send a message to the local AI model."""
    message = request.message.strip()

    if not message:
        raise HTTPException(
            status_code=422,
            detail="Mesaj boş olamaz.",
        )

    history = []

    for item in request.history:
        role = item.role.strip().lower()

        if role not in {"user", "assistant"}:
            raise HTTPException(
                status_code=422,
                detail="Geçmiş mesajların rolü user veya assistant olmalıdır.",
            )

        history.append({
            "role": role,
            "content": item.content,
        })

    try:
        return chat_with_ai(
            message=message,
            history=history,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc
