from fastapi import FastAPI
from app.config import settings
from app.routers import chat


app = FastAPI(title="Mosaic")
app.include_router(chat.router)



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
    return{
        "message":"pinkuu"

    }
