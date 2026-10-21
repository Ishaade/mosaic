"""
Authentication: register, login, me, delete account.

Logout is client-side only (delete the JWT). See stage-A notes.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import crud
from app.db.models import User
from app.db.session import get_db
from app.deps import get_current_user
from app.rate_limit import limiter
from app.schemas import (
    DeleteUserDataOut,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.services.memory_store import get_memory_store
from app.services.passwords import hash_password, verify_password
from app.services.tokens import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

# Same message for unknown email AND wrong password — no account enumeration
_INVALID_CREDS = "Invalid email or password"


@router.post("/register", response_model=UserOut, status_code=201)
@limiter.limit("5/minute")
def register(request: Request, body: RegisterRequest, db: Session = Depends(get_db)):
    """
    Create an account. Email is stored lowercase.
    Rate-limited to slow bulk signups / credential stuffing.
    """
    if crud.get_user_by_email(db, body.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = crud.create_user(
        db,
        email=body.email,
        password_hash=hash_password(body.password),
        name=body.name,
    )
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    """
    Exchange email+password for a signed JWT.
    Always the same error on failure so attackers can't probe which emails exist.
    """
    user = crud.get_user_by_email(db, body.email)
    # Timing side-channels are a deeper topic; for a portfolio we keep it simple.
    if user is None or not verify_password(user.password_hash, body.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_CREDS,
        )

    token, expires_in = create_access_token(user_id=user.id, email=user.email)
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user (from the Bearer token)."""
    return current_user


@router.delete("/me", response_model=DeleteUserDataOut)
def delete_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete this account and ALL related data (SQL + Chroma vectors).

    Irreversible. The JWT may still look valid until expiry, but /me and
    protected routes will 401 once the user row is gone.
    """
    user_id = current_user.id
    memories_deleted = get_memory_store().delete_user(user_id)
    sql_counts = crud.delete_all_sql_for_user(db, user_id)
    return DeleteUserDataOut(
        user_id=user_id,
        sql=sql_counts,
        memories_deleted=memories_deleted,
    )
