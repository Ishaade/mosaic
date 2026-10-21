"""
Chat endpoints: JSON (`POST /chat`) and Server-Sent Events (`POST /chat/stream`).

User identity always comes from the JWT via `get_current_user`.
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
from app.deps import get_current_user
from app.personas.prompts import get_system_prompt
from app.schemas import ChatRequest, ChatResponse, PersonaSuggestion
from app.services.helplines import THERAPIST_DISCLAIMER
from app.services.llm import LLMError, generate_reply, stream_reply
from app.services.memory_extract import extract_facts
from app.services.memory_store import format_memories_for_prompt, get_memory_store
from app.services.prompt_guard import wrap_history_for_llm
from app.services.router import (
    filter_suggestion,
    should_attempt_routing,
    suggest_persona,
)
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
    crisis: bool = False
    crisis_layer: str | None = None
    crisis_reply: str | None = None
    system_prompt: str = ""
    llm_messages: list[dict[str, str]] | None = None
    # Stage B: optional persona nudge (never auto-applied)
    suggestion: PersonaSuggestion | None = None
    # Prior turns for the router (excludes the just-saved user message)
    _prior_for_router: list[dict[str, str]] | None = None


async def _prepare_chat(
    req: ChatRequest,
    db: Session,
    user: User,
) -> _PreparedChat:
    disclaimer = THERAPIST_DISCLAIMER if req.persona == "therapist" else None
    region = req.region or settings.default_region

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

    # Snapshot prior history BEFORE saving this turn (for the persona router)
    prior_msgs = crud.list_messages(db, conversation.id)
    prior_for_router = [{"role": m.role, "content": m.content} for m in prior_msgs[-4:]]

    crud.add_message(db, conversation.id, role="user", content=req.message)

    prepared = _PreparedChat(
        user=user,
        conversation=conversation,
        disclaimer=disclaimer,
        region=region,
        _prior_for_router=prior_for_router,
    )

    # --- Safety gate: crisis ALWAYS wins — skip routing entirely ------------
    decision = await check_crisis(req.message, region=region)
    if decision.crisis:
        crud.add_message(
            db, conversation.id, role="assistant", content=decision.reply or ""
        )
        prepared.crisis = True
        prepared.crisis_layer = decision.layer
        prepared.crisis_reply = decision.reply
        return prepared

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
    prepared.llm_messages = wrap_history_for_llm(raw)
    return prepared


async def _maybe_attach_suggestion(
    req: ChatRequest,
    db: Session,
    prepared: _PreparedChat,
) -> None:
    """
    Best-effort persona suggestion. Never raises into the chat path.
    Skipped on crisis (caller must not invoke). Anti-nag via message cooldown.
    """
    try:
        user_turns = crud.count_user_messages(db, prepared.conversation.id)
        if not should_attempt_routing(user_turns):
            return
        raw = await suggest_persona(
            message=req.message,
            current_persona=req.persona,
            recent_messages=prepared._prior_for_router,
        )
        out = filter_suggestion(raw, current_persona=req.persona)
        if out is not None:
            prepared.suggestion = PersonaSuggestion(
                persona=out.persona,
                reason=out.reason,
                confidence=out.confidence,
            )
    except Exception:
        logger.exception("Persona routing failed; continuing without suggestion")


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
async def chat(
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prepared = await _prepare_chat(req, db, current_user)

    if prepared.crisis:
        return ChatResponse(
            persona=req.persona,
            reply=prepared.crisis_reply or "",
            crisis=True,
            crisis_layer=prepared.crisis_layer,
            disclaimer=prepared.disclaimer,
            user_id=prepared.user.id,
            conversation_id=prepared.conversation.id,
            suggestion=None,
        )

    # Suggest before the (slower) reply so latency is sequential but clear
    await _maybe_attach_suggestion(req, db, prepared)

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
        suggestion=prepared.suggestion,
    )


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/stream")
async def chat_stream(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Same logic as /chat, but tokens arrive as Server-Sent Events.
    `suggestion` (if any) is included on the meta event.
    """
    user_id = current_user.id

    async def event_gen() -> AsyncIterator[str]:
        db = SessionLocal()
        try:
            user = crud.get_user(db, user_id)
            if user is None:
                yield _sse(
                    {"type": "error", "detail": "Not authenticated", "status": 401}
                )
                return

            try:
                prepared = await _prepare_chat(req, db, user)
            except HTTPException as exc:
                detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
                yield _sse(
                    {"type": "error", "detail": detail, "status": exc.status_code}
                )
                return

            if not prepared.crisis:
                await _maybe_attach_suggestion(req, db, prepared)

            suggestion_payload = None
            if prepared.suggestion is not None:
                suggestion_payload = prepared.suggestion.model_dump()

            meta = {
                "type": "meta",
                "persona": req.persona,
                "user_id": prepared.user.id,
                "conversation_id": prepared.conversation.id,
                "crisis": prepared.crisis,
                "crisis_layer": prepared.crisis_layer,
                "disclaimer": prepared.disclaimer,
                "suggestion": suggestion_payload,
            }
            yield _sse(meta)

            if prepared.crisis:
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
            "X-Accel-Buffering": "no",
        },
    )
