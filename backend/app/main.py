from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings
from app.db import models  # noqa: F401  (importing registers the tables on Base)
from app.db.session import Base, engine
from app.rate_limit import limiter
from app.routers import auth, chat, conversations, memories

# Creates missing tables; never alters existing ones (Alembic comes later)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Mosaic")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    # Authorization header must be allowed for Bearer tokens from the browser
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(memories.router)


@app.get("/health")
async def health():
    # Never return secrets — only whether they look configured
    return {
        "status": "ok",
        "env": settings.app_env,
        "llm_key_configured": bool(settings.llm_api_key),
        "jwt_configured": bool(settings.jwt_secret),
    }


@app.get("/ping")
async def ping():
    return {"message": "pinkuu"}
