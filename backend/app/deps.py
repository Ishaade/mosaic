"""
Shared FastAPI dependencies.

`get_current_user` is the gate for every protected endpoint: the user id
ALWAYS comes from a verified JWT, never from the request body or query string.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import ExpiredSignatureError, InvalidTokenError
from sqlalchemy.orm import Session

from app.db import crud
from app.db.models import User
from app.db.session import get_db
from app.services.tokens import decode_access_token

# auto_error=False so we can return a consistent 401 message ourselves
_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """
    Read `Authorization: Bearer <token>`, verify it, load the User row.

    Returns 401 (not 404) when the token is missing/bad — the client should
    re-authenticate. We still use 404 for *resource* ownership misses elsewhere.
    """
    if creds is None or creds.scheme.lower() != "bearer" or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(creds.credentials)
        user_id = int(payload["sub"])
    except (ExpiredSignatureError, InvalidTokenError, KeyError, ValueError, TypeError):
        # Same generic message for expired, tampered, or malformed tokens
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    user = crud.get_user(db, user_id)
    if user is None:
        # Token was valid once, but the account was deleted
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
