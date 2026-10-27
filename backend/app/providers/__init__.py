from __future__ import annotations

from ..config import Settings
from .anthropic_pipeline import AnthropicPipelineProvider
from .base import VideoProvider
from .fal_kling import FalKlingProvider
from .mock import MockProvider
from .openai_sora import OpenAISoraProvider


def get_provider(settings: Settings) -> VideoProvider:
    name = (settings.video_provider or "mock").strip().lower()

    if name == "anthropic":
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "VIDEO_PROVIDER=anthropic requires ANTHROPIC_API_KEY. "
                "Also set FAL_KEY for real Kling video (otherwise local ffmpeg mock is used)."
            )
        return AnthropicPipelineProvider(
            anthropic_api_key=settings.anthropic_api_key,
            fal_key=settings.fal_key,
            anthropic_model=settings.anthropic_model,
        )

    if name == "fal":
        if not settings.fal_key:
            raise RuntimeError(
                "VIDEO_PROVIDER=fal requires FAL_KEY. "
                "Get a key at https://fal.ai — or use VIDEO_PROVIDER=mock."
            )
        return FalKlingProvider(settings.fal_key)

    if name == "openai":
        if not settings.openai_api_key:
            raise RuntimeError(
                "VIDEO_PROVIDER=openai requires OPENAI_API_KEY. "
                "Note: OpenAI shut down /v1/videos on 2026-09-24 — prefer anthropic+fal or mock."
            )
        return OpenAISoraProvider(settings.openai_api_key, settings.openai_base_url)

    if name == "mock":
        return MockProvider()

    raise RuntimeError(
        f"Unknown VIDEO_PROVIDER={name!r}. Use 'mock', 'anthropic', 'fal', or 'openai'."
    )
