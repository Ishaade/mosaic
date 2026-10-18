from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import crud
from app.db.session import get_db
from app.schemas import DeleteUserDataOut, MemoryOut, UserCreate, UserOut
from app.services.memory_store import get_memory_store

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, db: Session = Depends(get_db)):
    """
    Create a lightweight user row and return its id.

    This is NOT authentication — anyone who knows an id can claim it.
    A real app would use JWT/OAuth and never trust a client-supplied user_id.
    """
    return crud.create_user(db, name=body.name)


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = crud.get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/{user_id}/memories", response_model=list[MemoryOut])
def list_memories(user_id: int, db: Session = Depends(get_db)):
    """List vector memories for this user (privacy / transparency)."""
    user = crud.get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    hits = get_memory_store().list_for_user(user_id)
    return [
        MemoryOut(
            id=h.id,
            text=h.text,
            user_id=h.user_id,
            persona=h.persona,
            kind=h.kind,
            created_at=h.created_at,
        )
        for h in hits
    ]


@router.delete("/{user_id}/data", response_model=DeleteUserDataOut)
def delete_all_user_data(user_id: int, db: Session = Depends(get_db)):
    """
    Privacy wipe: delete SQL rows AND vector memories for this user.

    Still not real auth — knowing the id is enough. Documented limitation.
    """
    user = crud.get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    memories_deleted = get_memory_store().delete_user(user_id)
    sql_counts = crud.delete_all_sql_for_user(db, user_id)
    return DeleteUserDataOut(
        user_id=user_id,
        sql=sql_counts,
        memories_deleted=memories_deleted,
    )
