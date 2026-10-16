from fastapi import APIRouter

from app.personas.prompts import get_system_prompt
from app.schemas import ChatRequest, ChatResponse
from app.services.llm import generate_reply
from app.services.safety import CRISIS_REPLY, THERAPIST_DISCLAIMER, is_crisis

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest):
    disclaimer = THERAPIST_DISCLAIMER if req.persona == "therapist" else None

    # Safety gate: runs BEFORE the LLM, for every persona
    if is_crisis(req.message):
        return ChatResponse(
            persona=req.persona, reply=CRISIS_REPLY, crisis=True, disclaimer=disclaimer
        )

    reply = await generate_reply(
        system_prompt=get_system_prompt(req.persona),
        user_message=req.message,
    )
    return ChatResponse(persona=req.persona, reply=reply, disclaimer=disclaimer)