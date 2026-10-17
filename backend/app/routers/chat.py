from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import crud
from app.db.session import get_db
from app.personas.prompts import get_system_prompt
from app.schemas import ChatRequest, ChatResponse
from app.services.llm import LLMError, generate_reply
from app.services.safety import CRISIS_REPLY, THERAPIST_DISCLAIMER, is_crisis

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest, db: Session = Depends(get_db)):
    disclaimer = THERAPIST_DISCLAIMER if req.persona == "therapist" else None

    # --- Resolve user -------------------------------------------------------
    user = crud.get_user(db, req.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # --- Resolve or create conversation -------------------------------------
    if req.conversation_id is None:
        conversation = crud.create_conversation(db, user_id=user.id, persona=req.persona)
    else:
        conversation = crud.get_conversation(db, req.conversation_id)
        if conversation is None or conversation.user_id != user.id:
            raise HTTPException(status_code=404, detail="Conversation not found")
        # Keep persona consistent within one conversation thread
        if conversation.persona != req.persona:
            raise HTTPException(
                status_code=400,
                detail="persona does not match this conversation; start a new one",
            )

    # --- Persist the user turn (including crisis messages) ------------------
    # We save before the LLM so a crash mid-request still leaves the user's words.
    crud.add_message(db, conversation.id, role="user", content=req.message)

    # --- Safety gate: BEFORE the LLM, every persona -------------------------
    if is_crisis(req.message):
        crud.add_message(db, conversation.id, role="assistant", content=CRISIS_REPLY)
        return ChatResponse(
            persona=req.persona,
            reply=CRISIS_REPLY,
            crisis=True,
            disclaimer=disclaimer,
            user_id=user.id,
            conversation_id=conversation.id,
        )

    # --- Load recent history (includes the message we just saved) -----------
    history = crud.get_recent_messages_for_llm(db, conversation.id)
    llm_messages = [{"role": m.role, "content": m.content} for m in history]

    try:
        reply = await generate_reply(
            system_prompt=get_system_prompt(req.persona),
            messages=llm_messages,
        )
    except LLMError as exc:
        # Never expose raw provider errors / tracebacks / keys to the client
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    crud.add_message(db, conversation.id, role="assistant", content=reply)

    return ChatResponse(
        persona=req.persona,
        reply=reply,
        disclaimer=disclaimer,
        user_id=user.id,
        conversation_id=conversation.id,
    )
