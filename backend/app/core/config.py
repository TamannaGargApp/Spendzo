from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_url: str = "mongodb://localhost:27017"
    mongo_db: str = "ledger"
    jwt_secret: str = "change-me"
    access_minutes: int = 30
    refresh_days: int = 7
    admin_email: str | None = None
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen3:4b"
    upload_dir: str = "uploads"
    max_upload_mb: int = 5
    # comma separated origins allowed to call the API (the frontend)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"


settings = Settings()
