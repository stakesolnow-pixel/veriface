from __future__ import annotations

import asyncio
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from .base import ProviderResult, VideoProvider


class MockProvider(VideoProvider):
    """Local ffmpeg head-turn simulation — no Emergent / OpenAI dependency."""

    name = "mock"

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
        out_dir.mkdir(parents=True, exist_ok=True)
        video_path = out_dir / "verification.mp4"
        width, height = (int(x) for x in size.lower().split("x"))
        duration = int(seconds)

        await asyncio.to_thread(
            _render_head_turn,
            image_path,
            video_path,
            width,
            height,
            duration,
        )

        if not video_path.exists() or video_path.stat().st_size < 1000:
            return ProviderResult(
                status="failed",
                message="Local render failed",
                error="ffmpeg did not produce a usable mp4. Is ffmpeg installed?",
            )

        return ProviderResult(
            status="completed",
            message="Verification video ready",
            progress=100.0,
            video_path=video_path,
            provider_job_id=f"mock-{video_path.stem}",
        )

    async def poll(self, *, provider_job_id: str, out_dir: Path) -> ProviderResult:
        video_path = out_dir / "verification.mp4"
        if video_path.exists():
            return ProviderResult(
                status="completed",
                message="Verification video ready",
                progress=100.0,
                video_path=video_path,
                provider_job_id=provider_job_id,
            )
        return ProviderResult(
            status="failed",
            message="Job missing",
            error="Mock job output not found",
            provider_job_id=provider_job_id,
        )


def _render_head_turn(
    image_path: Path,
    video_path: Path,
    width: int,
    height: int,
    duration: int,
) -> None:
    """Synthesize a 12s left→right look by yawing a portrait on a soft backdrop."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found on PATH")

    fps = 16
    total_frames = duration * fps
    with tempfile.TemporaryDirectory(prefix="veriface-frames-") as tmp:
        frame_dir = Path(tmp)
        src = Image.open(image_path).convert("RGB")
        # Cover 1280x720 crop
        scale = max(width / src.width, height / src.height) * 1.15
        resized = src.resize((int(src.width * scale), int(src.height * scale)), Image.Resampling.LANCZOS)
        left = (resized.width - width) // 2
        top = (resized.height - height) // 2
        base = resized.crop((left, top, left + width, top + height))

        for i in range(total_frames):
            t = i / max(total_frames - 1, 1)
            # Face camera → look left → look right → face camera
            if t < 0.12:
                yaw = 0.0
            elif t < 0.38:
                yaw = -22.0 * _ease((t - 0.12) / 0.26)
            elif t < 0.50:
                yaw = -22.0
            elif t < 0.76:
                yaw = -22.0 + 44.0 * _ease((t - 0.50) / 0.26)
            elif t < 0.88:
                yaw = 22.0
            else:
                yaw = 22.0 * (1.0 - _ease((t - 0.88) / 0.12))

            frame = _yaw_frame(base, yaw)
            frame.save(frame_dir / f"frame_{i:05d}.jpg", quality=92)

        cmd = [
            "ffmpeg",
            "-y",
            "-framerate",
            str(fps),
            "-i",
            str(frame_dir / "frame_%05d.jpg"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-crf",
            "20",
            str(video_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)


def _ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 0.5 - 0.5 * math.cos(math.pi * x)


def _yaw_frame(base: Image.Image, yaw_deg: float) -> Image.Image:
    """Approximate yaw with horizontal squeeze + pan (fast, no per-pixel loops)."""
    w, h = base.size
    yaw = math.radians(yaw_deg)
    scale_x = max(0.84, abs(math.cos(yaw)))
    new_w = max(2, int(w * scale_x))
    squeezed = base.resize((new_w, h), Image.Resampling.BILINEAR)
    canvas = Image.new("RGB", (w, h), (24, 22, 20))
    offset_x = (w - new_w) // 2 + int(math.sin(yaw) * w * 0.08)
    canvas.paste(squeezed, (offset_x, 0))
    return canvas
