import httpx
import ollama
from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import CurrentUser, get_current_user
from app.models.schemas import ChatIn
from app.services import chatbot

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("")
async def chat(body: ChatIn, user: CurrentUser = Depends(get_current_user)):
    try:
        reply = await chatbot.answer(user, body.message, body.history)
    except (httpx.HTTPError, ollama.ResponseError, ConnectionError):
        raise HTTPException(
            503, "The assistant is offline. Start Ollama and run: ollama pull qwen3:4b"
        )
    return {"reply": reply}
