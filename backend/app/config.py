from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # openai | mock
    video_provider: str = "mock"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"

    data_dir: Path = Path(__file__).resolve().parent.parent / "data"
    max_upload_bytes: int = 12 * 1024 * 1024
    default_model: str = "sora-2"
    video_seconds: str = "12"
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
