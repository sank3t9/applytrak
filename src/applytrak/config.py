from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    redis_url: str

    anthropic_api_key: str
    anthropic_model_parse: str = "claude-haiku-4-5"
    anthropic_model_score: str = "claude-sonnet-4-6"

    voyage_api_key: str = ""
    embedding_model: str = "voyage-3"

    langsmith_api_key: str = ""
    langsmith_project: str = "applytrak"

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    relevance_threshold: float = Field(0.65, ge=0.0, le=1.0)
    digest_max_items: int = Field(10, ge=1, le=50)
    dedupe_similarity_threshold: float = Field(0.92, ge=0.0, le=1.0)
    fetch_interval_hours: int = Field(4, ge=1)


settings = Settings()
