"""
Signed JWT access tokens.

Stateless: the server does not store issued tokens. Logout = client deletes
the token. Stolen tokens remain valid until `exp` — see stage-A notes.
"""

from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings


def create_access_token(*, user_id: int, email: str) -> tuple[str, int]:
    """
    Return (token_string, expires_in_seconds).

    Claims:
      sub  — user id as string (JWT convention)
      email — handy for debugging /me without an extra lookup (still verify in DB)
      exp  — expiry unix timestamp
    """
    expires_in = settings.jwt_expire_minutes * 60
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    # PyJWT>=2 returns str; older returned bytes — normalize just in case
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token, expires_in


def decode_access_token(token: str) -> dict:
    """
    Verify signature + expiry. Raises jwt.PyJWTError subclasses on failure.
    Caller maps those to HTTP 401.
    """
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )
