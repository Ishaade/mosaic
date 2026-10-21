from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Each field is filled from an environment variable of the same name
    # (case-insensitive). Types are validated at startup.
    llm_api_key: str = ""
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "openai/gpt-oss-safeguard-20b"
    app_env: str = "development"
    # Folder for ChromaDB's on-disk vector index (created automatically)
    chroma_path: str = "./chroma_data"
    # Helpline region code: IN | US | GB | … (see app.services.helplines)
    default_region: str = "IN"

    # --- Auth (Stage A) -------------------------------------------------------
    # REQUIRED — no default. App refuses to start if JWT_SECRET is missing.
    # Add to .env (never commit secrets): JWT_SECRET=some-long-random-string
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # --- Smart routing (Stage B) ---------------------------------------------
    # Only surface a persona suggestion when confidence >= this (0–1)
    routing_confidence_threshold: float = 0.65
    # Suggest at most once every N user turns in a conversation (anti-nag)
    routing_cooldown_messages: int = 3

    # Tell pydantic to also read from the .env file
    model_config = SettingsConfigDict(env_file=".env")


# One shared instance that the rest of the app imports
settings = Settings()
