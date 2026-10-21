"""Authenticated memory list/delete endpoints (privacy / transparency)."""

from fastapi import APIRouter, Depends, HTTPException

from app.db.models import User
from app.deps import get_current_user
from app.schemas import DeleteUserDataOut, MemoryOut
from app.services.memory_store import get_memory_store

router = APIRouter(prefix="/memories", tags=["memories"])


def _to_out(h) -> MemoryOut:
    return MemoryOut(
        id=h.id,
        text=h.text,
        user_id=h.user_id,
        persona=h.persona,
        kind=h.kind,
        created_at=h.created_at,
    )


@router.get("", response_model=list[MemoryOut])
def list_my_memories(current_user: User = Depends(get_current_user)):
    """List vector memories for the logged-in user only."""
    hits = get_memory_store().list_for_user(current_user.id)
    return [_to_out(h) for h in hits]


@router.delete("/{memory_id}")
def delete_one_memory(
    memory_id: str,
    current_user: User = Depends(get_current_user),
):
    """Delete a single memory chunk. 404 if missing or owned by someone else."""
    ok = get_memory_store().delete_one(memory_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"deleted": True, "id": memory_id}


@router.delete("", response_model=DeleteUserDataOut)
def delete_all_memories(current_user: User = Depends(get_current_user)):
    """Wipe vector memories only — SQL chats stay. Account wipe is DELETE /auth/me."""
    memories_deleted = get_memory_store().delete_user(current_user.id)
    return DeleteUserDataOut(
        user_id=current_user.id,
        sql={"messages": 0, "conversations": 0, "users": 0},
        memories_deleted=memories_deleted,
    )
