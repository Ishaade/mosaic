"""
Shared slowapi limiter instance.

Attached to `app.state.limiter` in main.py. Auth routes decorate with
`@limiter.limit(...)` and must accept a `Request` parameter.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Key by client IP — good enough for a portfolio demo; behind a reverse proxy
# you'd trust X-Forwarded-For carefully instead.
limiter = Limiter(key_func=get_remote_address)
