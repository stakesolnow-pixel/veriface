from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

import httpx

from ..prompt import LIVENESS_PROMPT
from .base import ProviderResult, VideoProvider
from .fal_kling import FalKlingProvider
from .mock import MockProvider


class AnthropicPipelineProvider(VideoProvider):
    """Claude crafts the liveness prompt; Kling (fal) renders the video.

    Anthropic has no video-generation API. This provider:
      1. Sends the portrait to Claude (vision) for a strict motion prompt
      2. Renders with fal.ai Kling when FAL_KEY is set
      3. Falls back to local ffmpeg mock if FAL_KEY is missing
    """

    name = "anthropic"

    def __init__(
        self,
        anthropic_api_key: str,
        fal_key: str | None = None,
        anthropic_model: str = "claude-sonnet-4-20250514",
    ) -> None:
        if not anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for VIDEO_PROVIDER=anthropic")
        self.anthropic_api_key = anthropic_api_key
        self.anthropic_model = anthropic_model
        self._renderer: VideoProvider
        if fal_key:
            self._renderer = FalKlingProvider(fal_key)
            self._renderer_name = "kling"
        else:
            self._renderer = MockProvider()
            self._renderer_name = "mock"

    async def start(
        self,
        *,
        image_path: Path,
        model: str,
        prompt: str,
        seconds: str,
        size: str,
        out_dir: Path,
    ) -> ProviderResult:
        crafted = await self._claude_liveness_prompt(image_path, fallback=prompt or LIVENESS_PROMPT)
        result = await self._renderer.start(
            image_path=image_path,
            model=model,
            prompt=crafted,
            seconds=seconds,
            size=size,
            out_dir=out_dir,
        )
        if result.status == "processing":
            suffix = "Kling" if self._renderer_name == "kling" else "local mock"
            result.message = f"Claude prompt ready · generating on {suffix}…"
        elif result.status == "completed" and self._renderer_name == "mock":
            result.message = "Verification video ready (Claude-guided local mock — set FAL_KEY for real AI video)"
        return result

    async def poll(self, *, provider_job_id: str, out_dir: Path) -> ProviderResult:
        return await self._renderer.poll(provider_job_id=provider_job_id, out_dir=out_dir)

    async def _claude_liveness_prompt(self, image_path: Path, fallback: str) -> str:
        mime = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
        b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        system = (
            "You write short, strict image-to-video prompts for KYC liveness clips. "
            "Output ONLY the prompt text — no preamble, no quotes."
        )
        user_text = (
            "This portrait will be the first frame of an identity-verification video. "
            "Write a single prompt (max 120 words) that keeps the SAME person, clothing, "
            "and background, and directs a natural head-turn proof-of-life: face camera, "
            "slowly look left and hold, look right and hold, return to center. "
            "Neutral expression, locked frontal camera, medium close-up, photorealistic, "
            "no text, no morphing, no identity change."
        )
        payload = {
            "model": self.anthropic_model,
            "max_tokens": 300,
            "system": system,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime,
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": user_text},
                    ],
                }
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json=payload,
                )
            if resp.status_code >= 400:
                return fallback
            data = resp.json()
            parts = data.get("content") or []
            text = "".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()
            return text or fallback
        except Exception:
            return fallback
