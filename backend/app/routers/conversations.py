from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import crud
from app.db.session import get_db
from app.schemas import ConversationOut, MessageOut

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationOut])
def list_conversations(
    user_id: int = Query(..., description="Owner of the conversations"),
    db: Session = Depends(get_db),
):
    """List one user's conversations. Caller must pass their own user_id."""
    user = crud.get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return crud.list_conversations_for_user(db, user_id)


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
def list_messages(
    conversation_id: int,
    user_id: int = Query(..., description="Must own this conversation"),
    db: Session = Depends(get_db),
):
    """
    Return messages for a conversation, but only if `user_id` owns it.

    Ownership check stops one portfolio-demo user from reading another's
    history by guessing ids. This is still not real auth — a forged
    user_id would pass. JWT/session cookies would replace this later.
    """
    conversation = crud.get_conversation(db, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conversation.user_id != user_id:
        # 404 (not 403) so we don't confirm the conversation exists to strangers
        raise HTTPException(status_code=404, detail="Conversation not found")
    return crud.list_messages(db, conversation_id)
