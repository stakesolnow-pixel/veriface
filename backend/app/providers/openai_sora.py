from __future__ import annotations

import mimetypes
from pathlib import Path

import httpx

from .base import ProviderResult, VideoProvider


class OpenAISoraProvider(VideoProvider):
    """OpenAI Videos API (Sora 2). Requires OPENAI_API_KEY.

    Note: OpenAI shut down the public Sora Videos API on 2026-09-24.
    This provider is kept for accounts/endpoints that still expose /v1/videos,
    or for drop-in compatible proxies via OPENAI_BASE_URL.
    """

    name = "openai"

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1") -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for the openai provider")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

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
        mime = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
        async with httpx.AsyncClient(timeout=120.0) as client:
            with image_path.open("rb") as fh:
                files = {
                    "input_reference": (image_path.name, fh, mime),
                }
                data = {
                    "prompt": prompt,
                    "model": model,
                    "seconds": str(seconds),
                    "size": size,
                }
                resp = await client.post(
                    f"{self.base_url}/videos",
                    headers=self._headers(),
                    data=data,
                    files=files,
                )
            if resp.status_code >= 400:
                detail = _extract_error(resp)
                return ProviderResult(
                    status="failed",
                    message="Sora 2 rejected the request",
                    error=detail,
                )
            body = resp.json()
            job_id = body.get("id")
            status = body.get("status", "queued")
            return ProviderResult(
                status="processing" if status != "completed" else "completed",
                message=_status_message(status, body.get("progress")),
                progress=float(body.get("progress") or 0),
                provider_job_id=job_id,
            )

    async def poll(self, *, provider_job_id: str, out_dir: Path) -> ProviderResult:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.get(
                f"{self.base_url}/videos/{provider_job_id}",
                headers=self._headers(),
            )
            if resp.status_code >= 400:
                return ProviderResult(
                    status="failed",
                    message="Failed to poll Sora 2",
                    error=_extract_error(resp),
                    provider_job_id=provider_job_id,
                )
            body = resp.json()
            status = body.get("status", "processing")
            progress = float(body.get("progress") or 0)

            if status in {"failed", "cancelled", "error"}:
                err = body.get("error") or {}
                return ProviderResult(
                    status="failed",
                    message="Sora 2 couldn't produce the verification clip. Try a clearer front-facing photo.",
                    error=err.get("message") if isinstance(err, dict) else str(err) or "Generation failed",
                    progress=progress,
                    provider_job_id=provider_job_id,
                )

            if status != "completed":
                return ProviderResult(
                    status="processing",
                    message=_status_message(status, progress),
                    progress=progress,
                    provider_job_id=provider_job_id,
                )

            # Download content
            out_dir.mkdir(parents=True, exist_ok=True)
            video_path = out_dir / "verification.mp4"
            content = await client.get(
                f"{self.base_url}/videos/{provider_job_id}/content",
                headers=self._headers(),
            )
            if content.status_code >= 400:
                return ProviderResult(
                    status="failed",
                    message="Failed to download Sora 2 video",
                    error=_extract_error(content),
                    provider_job_id=provider_job_id,
                )
            video_path.write_bytes(content.content)
            return ProviderResult(
                status="completed",
                message="Verification video ready",
                progress=100.0,
                video_path=video_path,
                provider_job_id=provider_job_id,
            )


def _extract_error(resp: httpx.Response) -> str:
    try:
        data = resp.json()
        err = data.get("error") or data
        if isinstance(err, dict):
            return err.get("message") or err.get("detail") or resp.text[:400]
        return str(err)
    except Exception:
        return resp.text[:400] or f"HTTP {resp.status_code}"


def _status_message(status: str, progress: float | None) -> str:
    if status in {"queued", "pending"}:
        return "Job queued · waiting for Sora 2…"
    if status in {"in_progress", "processing", "running"}:
        pct = f" · {int(progress)}%" if progress else ""
        return f"Generating on Sora 2{pct}"
    if status == "completed":
        return "Verification video ready"
    return f"Status: {status}"
