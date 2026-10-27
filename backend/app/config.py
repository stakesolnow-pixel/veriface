from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # mock | anthropic | fal | openai
    video_provider: str = "mock"

    # Anthropic (prompt crafting for VIDEO_PROVIDER=anthropic)
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-20250514"

    # fal.ai Kling (actual image-to-video render)
    fal_key: str | None = None

    # Legacy OpenAI Videos API (shutdown 2026-09-24; only for compatible proxies)
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"

    data_dir: Path = Path(__file__).resolve().parent.parent / "data"
    max_upload_bytes: int = 12 * 1024 * 1024
    default_model: str = "sora-2"
    video_seconds: str = "10"
    video_size: str = "1280x720"
    poll_interval_seconds: float = 3.0
    job_ttl_seconds: int = 60 * 60
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
