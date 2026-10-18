"""
Chat endpoints: JSON (`POST /chat`) and Server-Sent Events (`POST /chat/stream`).
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.db import crud
from app.db.models import Conversation, User
from app.db.session import SessionLocal, get_db
from app.personas.prompts import get_system_prompt
from app.schemas import ChatRequest, ChatResponse
from app.services.helplines import THERAPIST_DISCLAIMER
from app.services.llm import LLMError, generate_reply, stream_reply
from app.services.memory_extract import extract_facts
from app.services.memory_store import format_memories_for_prompt, get_memory_store
from app.services.prompt_guard import wrap_history_for_llm
from app.services.safety import check_crisis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@dataclass
class _PreparedChat:
    """Shared setup for both JSON and streaming responses."""

    user: User
    conversation: Conversation
    disclaimer: str | None
    region: str
    # Populated when safety gate fires
    crisis: bool = False
    crisis_layer: str | None = None
    crisis_reply: str | None = None
    system_prompt: str = ""
    llm_messages: list[dict[str, str]] | None = None


async def _prepare_chat(req: ChatRequest, db: Session) -> _PreparedChat:
    disclaimer = THERAPIST_DISCLAIMER if req.persona == "therapist" else None
    region = req.region or settings.default_region

    user = crud.get_user(db, req.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if req.conversation_id is None:
        conversation = crud.create_conversation(
            db, user_id=user.id, persona=req.persona
        )
    else:
        conversation = crud.get_conversation(db, req.conversation_id)
        if conversation is None or conversation.user_id != user.id:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if conversation.persona != req.persona:
            raise HTTPException(
                status_code=400,
                detail="persona does not match this conversation; start a new one",
            )

    # Persist user turn first (including crisis) so history survives crashes
    crud.add_message(db, conversation.id, role="user", content=req.message)

    prepared = _PreparedChat(
        user=user,
        conversation=conversation,
        disclaimer=disclaimer,
        region=region,
    )

    # --- Safety gate (keywords → LLM classifier) BEFORE chat LLM ------------
    decision = await check_crisis(req.message, region=region)
    if decision.crisis:
        crud.add_message(
            db, conversation.id, role="assistant", content=decision.reply or ""
        )
        prepared.crisis = True
        prepared.crisis_layer = decision.layer
        prepared.crisis_reply = decision.reply
        return prepared  # no memory extract on crisis

    # --- RAG ----------------------------------------------------------------
    store = get_memory_store()
    try:
        hits = store.query(
            user_id=user.id,
            persona=req.persona,
            query_text=req.message,
        )
    except Exception:
        logger.exception("Memory retrieval failed; continuing without memories")
        hits = []

    prepared.system_prompt = get_system_prompt(req.persona) + format_memories_for_prompt(
        hits
    )
    history = crud.get_recent_messages_for_llm(db, conversation.id)
    raw = [{"role": m.role, "content": m.content} for m in history]
    # Delimit user turns so injection text is labeled as data
    prepared.llm_messages = wrap_history_for_llm(raw)
    return prepared


async def _store_reply_and_memories(
    *,
    db: Session,
    req: ChatRequest,
    prepared: _PreparedChat,
    reply: str,
) -> None:
    crud.add_message(db, prepared.conversation.id, role="assistant", content=reply)
    store = get_memory_store()
    try:
        facts = await extract_facts(
            user_message=req.message,
            assistant_reply=reply,
            persona=req.persona,
        )
        if facts:
            store.add_facts(
                user_id=prepared.user.id, persona=req.persona, facts=facts
            )
    except Exception:
        logger.exception("Memory extraction/store failed; reply already saved")


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest, db: Session = Depends(get_db)):
    prepared = await _prepare_chat(req, db)

    if prepared.crisis:
        return ChatResponse(
            persona=req.persona,
            reply=prepared.crisis_reply or "",
            crisis=True,
            crisis_layer=prepared.crisis_layer,
            disclaimer=prepared.disclaimer,
            user_id=prepared.user.id,
            conversation_id=prepared.conversation.id,
        )

    try:
        reply = await generate_reply(
            system_prompt=prepared.system_prompt,
            messages=prepared.llm_messages or [],
        )
    except LLMError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    await _store_reply_and_memories(db=db, req=req, prepared=prepared, reply=reply)

    return ChatResponse(
        persona=req.persona,
        reply=reply,
        disclaimer=prepared.disclaimer,
        user_id=prepared.user.id,
        conversation_id=prepared.conversation.id,
    )


def _sse(payload: dict) -> str:
    """One SSE event line (JSON data)."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/stream")
async def chat_stream(req: ChatRequest):
    """
    Same logic as /chat, but tokens arrive as Server-Sent Events.

    Opens its own DB session inside the generator so the session stays alive
    for the whole stream (Depends(get_db) would close too early).

    Event shapes:
      {"type":"meta", ...}   — ids, crisis flag, disclaimer (always first)
      {"type":"token","text"} — incremental assistant text
      {"type":"done"}
      {"type":"error","detail"} — clean error, no secrets
    """

    async def event_gen() -> AsyncIterator[str]:
        db = SessionLocal()
        try:
            try:
                prepared = await _prepare_chat(req, db)
            except HTTPException as exc:
                detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
                yield _sse(
                    {"type": "error", "detail": detail, "status": exc.status_code}
                )
                return

            meta = {
                "type": "meta",
                "persona": req.persona,
                "user_id": prepared.user.id,
                "conversation_id": prepared.conversation.id,
                "crisis": prepared.crisis,
                "crisis_layer": prepared.crisis_layer,
                "disclaimer": prepared.disclaimer,
            }
            yield _sse(meta)

            if prepared.crisis:
                # Send the fixed reply as one token blob so the UI stays simple
                yield _sse({"type": "token", "text": prepared.crisis_reply or ""})
                yield _sse({"type": "done"})
                return

            collected: list[str] = []
            try:
                async for delta in stream_reply(
                    system_prompt=prepared.system_prompt,
                    messages=prepared.llm_messages or [],
                ):
                    collected.append(delta)
                    yield _sse({"type": "token", "text": delta})
            except LLMError as exc:
                yield _sse(
                    {"type": "error", "detail": exc.detail, "status": exc.status_code}
                )
                return

            reply = "".join(collected)
            if reply:
                await _store_reply_and_memories(
                    db=db, req=req, prepared=prepared, reply=reply
                )
            yield _sse({"type": "done"})
        finally:
            db.close()

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # nicer with some reverse proxies
        },
    )
