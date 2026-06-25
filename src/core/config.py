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

    # LLM provider — "groq" (free tier, to start) or "claude" (Haiku, quality)
    llm_provider: str = "groq"
    llm_max_tokens: int = 1024
    # Groq
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"
    # Anthropic / Claude
    anthropic_api_key: str = ""
    claude_model: str = "claude-haiku-4-5"

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "anticensorship_handbook"

    # Retrieval
    top_k: int = 5
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Telegram bot
    telegram_bot_token: str = ""
    telegram_proxy: str = ""  # optional: http(s)://host:port or socks5://host:port to reach api.telegram.org
    rate_limit_per_day: int = 5  # LLM calls per chat_id per day (FAQ answers are free)
    feedback_log: str = "data/feedback.jsonl"
    bot_footer: str = (
        "\n\n— не помогло или лень возиться? готовый сервис: @ExtenVPNBot"
    )


settings = Settings()