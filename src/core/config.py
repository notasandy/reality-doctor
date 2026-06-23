"""Application settings loaded from environment / .env."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "Reality Doctor"
    log_level: str = "INFO"

    # LLM (Groq for now; swappable to Claude Haiku at M4)
    groq_api_key: str
    groq_model: str = "llama-3.1-8b-instant"

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "anticensorship_handbook"

    # Retrieval
    top_k: int = 5
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"


settings = Settings()