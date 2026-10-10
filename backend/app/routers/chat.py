from fastapi import APIRouter

from app.schemas import ChatRequest, ChatResponse
from app.services.llm import generate_reply

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest):
    reply = await generate_reply(
        system_prompt=f"You are a helpful {req.persona}. Keep replies short.",
        user_message=req.message,
    )
    return ChatResponse(persona=req.persona, reply=reply)