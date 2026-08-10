from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    # Empty → no Redis: parse cache falls back to Postgres, rate limiter to in-process.
    redis_url: str = ""

    # Which provider handles parse/score/extract calls. Embeddings are separate below.
    llm_provider: Literal["anthropic", "gemini"] = "anthropic"

    anthropic_api_key: str = ""
    anthropic_model_parse: str = "claude-haiku-4-5"
    anthropic_model_score: str = "claude-sonnet-4-6"
    anthropic_rpm: int = Field(30, ge=1, description="Max Anthropic API calls per minute.")

    gemini_api_key: str = ""
    gemini_model_parse: str = "gemini-2.5-flash-lite"
    gemini_model_score: str = "gemini-2.5-flash"
    gemini_rpm: int = Field(8, ge=1, description="Max Gemini API calls per minute (free tier).")

    # Vectors from different providers/models are incomparable — one DB must stick to
    # one embedding model. Switching re-embeds the corpus (see run_embed provenance check).
    embedding_provider: Literal["voyage", "gemini"] = "voyage"
    voyage_api_key: str = ""
    embedding_model: str = "voyage-3"
    gemini_embedding_model: str = "gemini-embedding-001"

    langsmith_api_key: str = ""
    langsmith_project: str = "applytrak"

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    relevance_threshold: float = Field(0.65, ge=0.0, le=1.0)
    digest_max_items: int = Field(10, ge=1, le=50)
    dedupe_similarity_threshold: float = Field(0.92, ge=0.0, le=1.0)
    fetch_interval_hours: int = Field(4, ge=1)

    run_scheduler: bool = True
    # False hides the /run/* trigger endpoints (public demo deployments).
    expose_admin_endpoints: bool = True

    parse_cache_ttl_days: int = Field(30, ge=1)

    # Visitor match flow (demo).
    demo_resume_max_chars: int = Field(15_000, ge=1_000)
    match_top_k: int = Field(15, ge=1, le=30)
    match_recent_days: int = Field(45, ge=1)


settings = Settings()
