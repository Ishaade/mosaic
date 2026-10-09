from fastapi import APIRouter

from app.schemas import ChatRequest, ChatResponse

# A router is a group of related routes. The prefix is added to each path.
router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest):
    # req is already validated by the time we get here
    return ChatResponse(
        persona=req.persona,
        reply=f"[{req.persona}] You said: {req.message}",
    )