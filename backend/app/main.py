from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import models  # noqa: F401  (importing registers the tables on Base)
from app.db.session import Base, engine
from app.routers import chat, conversations, users

# Creates missing tables; never alters existing ones (Alembic comes in Phase 6)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Mosaic")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(users.router)
app.include_router(conversations.router)


@app.get("/health")
async def health():
    # Never return the key itself, only whether it's configured
    return {
        "status": "ok",
        "env": settings.app_env,
        "llm_key_configured": bool(settings.llm_api_key),
    }


@app.get("/ping")
async def ping():
    return {"message": "pinkuu"}
