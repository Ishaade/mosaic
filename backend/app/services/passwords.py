"""
Password hashing with argon2 (via argon2-cffi).

Why argon2: modern winner of the Password Hashing Competition; designed to
resist GPU/ASIC cracking better than older schemes. bcrypt is also fine;
we picked argon2 because the brief allowed either and argon2 is newer.
"""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# One shared hasher. Parameters are argon2-cffi defaults (safe for demos).
_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    """Return an argon2 hash string. Never log `plain`."""
    return _hasher.hash(plain)


def verify_password(password_hash: str, plain: str) -> bool:
    """True if `plain` matches the stored hash. Never log `plain`."""
    try:
        return _hasher.verify(password_hash, plain)
    except VerifyMismatchError:
        return False
    except Exception:
        # Corrupt hash / unexpected library error → treat as failed login
        return False
