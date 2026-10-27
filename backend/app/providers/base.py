from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProviderResult:
    status: str  # processing | completed | failed
    message: str
    progress: float = 0.0
    video_path: Path | None = None
    provider_job_id: str | None = None
    error: str | None = None


class VideoProvider(ABC):
    name: str

    @abstractmethod
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
        """Start generation. May complete immediately (mock) or return a provider job id."""

    @abstractmethod
    async def poll(self, *, provider_job_id: str, out_dir: Path) -> ProviderResult:
        """Poll an in-flight provider job."""
