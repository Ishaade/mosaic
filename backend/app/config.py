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
    # Tell pydantic to also read from the .env file
    model_config = SettingsConfigDict(env_file=".env")


# One shared instance that the rest of the app imports
settings = Settings()