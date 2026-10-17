"""
Database helpers for users, conversations, and messages.

Keeping SQL in one place makes the routers thin and easy to test.
These functions are sync: SQLAlchemy's default engine is sync, and FastAPI
runs sync path-operation code in a threadpool so the event loop stays free.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Conversation, Message, User

# Soft limit on how much past chat we feed the LLM.
# Character count is a simple stand-in for tokens (~4 chars ≈ 1 English token).
# Real tokenizers (tiktoken etc.) are more accurate but add a dependency.
HISTORY_CHAR_BUDGET = 6000


def create_user(db: Session, name: str | None = None) -> User:
    user = User(name=name)
    db.add(user)
    db.commit()
    db.refresh(user)  # reload so we get the auto-generated id
    return user


def get_user(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def create_conversation(db: Session, user_id: int, persona: str) -> Conversation:
    conversation = Conversation(user_id=user_id, persona=persona)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def get_conversation(db: Session, conversation_id: int) -> Conversation | None:
    return db.get(Conversation, conversation_id)


def list_conversations_for_user(db: Session, user_id: int) -> list[Conversation]:
    """Newest first — matches how a chat sidebar usually sorts."""
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.id.desc())
    )
    return list(db.scalars(stmt).all())


def add_message(
    db: Session,
    conversation_id: int,
    role: str,
    content: str,
) -> Message:
    message = Message(conversation_id=conversation_id, role=role, content=content)
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def list_messages(db: Session, conversation_id: int) -> list[Message]:
    """All messages in order — used by the history API for the UI."""
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.id.asc())
    )
    return list(db.scalars(stmt).all())


def get_recent_messages_for_llm(
    db: Session,
    conversation_id: int,
    budget: int = HISTORY_CHAR_BUDGET,
) -> list[Message]:
    """
    Return the newest messages that fit inside `budget` characters,
    still in chronological order (oldest → newest) for the LLM.

    Trade-off: we may drop older turns. That's intentional — long chats
    would otherwise blow the model's context window and cost more.
    """
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.id.desc())
    )
    newest_first = list(db.scalars(stmt).all())

    selected: list[Message] = []
    used = 0
    for msg in newest_first:
        length = len(msg.content)
        # Always keep at least one message so the latest user turn isn't dropped
        if selected and used + length > budget:
            break
        selected.append(msg)
        used += length

    selected.reverse()  # LLM expects oldest → newest
    return selected
