"""
Database helpers for users, conversations, and messages.

Keeping SQL in one place makes the routers thin and easy to test.
These functions are sync: SQLAlchemy's default engine is sync, and FastAPI
runs sync path-operation code in a threadpool so the event loop stays free.
"""

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import Conversation, Message, User

# Soft limit on how much past chat we feed the LLM.
# Character count is a simple stand-in for tokens (~4 chars ≈ 1 English token).
HISTORY_CHAR_BUDGET = 6000


def create_user(
    db: Session,
    *,
    email: str,
    password_hash: str,
    name: str | None = None,
) -> User:
    """Insert a registered user. `email` must already be lowercased by the caller."""
    user = User(email=email, password_hash=password_hash, name=name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_user_by_email(db: Session, email: str) -> User | None:
    """Lookup by normalized (lowercase) email."""
    stmt = select(User).where(User.email == email.lower())
    return db.scalars(stmt).first()


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


def count_user_messages(db: Session, conversation_id: int) -> int:
    """How many user turns exist — used for routing anti-nag cooldown."""
    stmt = (
        select(func.count())
        .select_from(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.role == "user",
        )
    )
    return int(db.scalar(stmt) or 0)


def get_recent_messages_for_llm(
    db: Session,
    conversation_id: int,
    budget: int = HISTORY_CHAR_BUDGET,
) -> list[Message]:
    """
    Return the newest messages that fit inside `budget` characters,
    still in chronological order (oldest → newest) for the LLM.
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
        if selected and used + length > budget:
            break
        selected.append(msg)
        used += length

    selected.reverse()
    return selected


def delete_all_sql_for_user(db: Session, user_id: int) -> dict[str, int]:
    """
    Wipe this user's SQL rows (messages → conversations → user).

    Order matters: messages reference conversations, conversations reference users.
    Vector memories are deleted separately by MemoryStore.delete_user.
    """
    conv_ids = list(
        db.scalars(select(Conversation.id).where(Conversation.user_id == user_id)).all()
    )
    messages_deleted = 0
    if conv_ids:
        result = db.execute(delete(Message).where(Message.conversation_id.in_(conv_ids)))
        messages_deleted = result.rowcount or 0

    conv_result = db.execute(delete(Conversation).where(Conversation.user_id == user_id))
    conversations_deleted = conv_result.rowcount or 0

    user_result = db.execute(delete(User).where(User.id == user_id))
    users_deleted = user_result.rowcount or 0

    db.commit()
    return {
        "messages": messages_deleted,
        "conversations": conversations_deleted,
        "users": users_deleted,
    }
