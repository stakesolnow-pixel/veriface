from __future__ import annotations

from ..config import Settings
from .base import VideoProvider
from .mock import MockProvider
from .openai_sora import OpenAISoraProvider


def get_provider(settings: Settings) -> VideoProvider:
    name = (settings.video_provider or "mock").strip().lower()
    if name == "openai":
        if not settings.openai_api_key:
            raise RuntimeError(
                "VIDEO_PROVIDER=openai requires OPENAI_API_KEY. "
                "Set the key, or use VIDEO_PROVIDER=mock for local ffmpeg rendering."
            )
        return OpenAISoraProvider(settings.openai_api_key, settings.openai_base_url)
    if name == "mock":
        return MockProvider()
    raise RuntimeError(f"Unknown VIDEO_PROVIDER={name!r}. Use 'mock' or 'openai'.")
