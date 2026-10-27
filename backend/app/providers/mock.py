from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

from .base import ProviderResult, VideoProvider


class MockProvider(VideoProvider):
    """Local ffmpeg head-turn simulation — no Emergent / OpenAI / Pillow dependency."""

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

        try:
            await asyncio.to_thread(
                _render_head_turn,
                image_path,
                video_path,
                width,
                height,
                duration,
            )
        except FileNotFoundError:
            return ProviderResult(
                status="failed",
                message="Local render failed",
                error="ffmpeg not found on PATH. Install ffmpeg and retry.",
            )
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or b"").decode("utf-8", errors="ignore")[-500:]
            return ProviderResult(
                status="failed",
                message="Local render failed",
                error=detail or str(exc),
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
    """Synthesize a left→right look using only ffmpeg (no Pillow / C build deps)."""
    if not shutil.which("ffmpeg"):
        raise FileNotFoundError("ffmpeg not found on PATH")

    # Oversized cover frame, then crop with a time-varying X offset that mimics yaw.
    # Timeline (t seconds): face → look left → look right → face.
    d = max(duration, 1)
    x_expr = (
        f"(iw-ow)/2"
        f"+if(lt(t\\,{d}*0.12)\\,0\\,"
        f"if(lt(t\\,{d}*0.38)\\,-90*sin(PI*(t-{d}*0.12)/({d}*0.26)/2)\\,"
        f"if(lt(t\\,{d}*0.50)\\,-90\\,"
        f"if(lt(t\\,{d}*0.76)\\,-90+180*((t-{d}*0.50)/({d}*0.26))\\,"
        f"if(lt(t\\,{d}*0.88)\\,90\\,"
        f"90*(1-(t-{d}*0.88)/({d}*0.12))"
        f")))))"
    )
    vf = (
        f"scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height}:{x_expr}:(ih-oh)/2,"
        f"fps=24,format=yuv420p"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        str(image_path),
        "-t",
        str(duration),
        "-vf",
        vf,
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
