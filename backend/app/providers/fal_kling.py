from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

import httpx

from .base import ProviderResult, VideoProvider

FAL_MODELS = {
    "sora-2": "fal-ai/kling-video/v2.5-turbo/pro/image-to-video",
    "sora-2-pro": "fal-ai/kling-video/v3/pro/image-to-video",
    "kling": "fal-ai/kling-video/v2.5-turbo/pro/image-to-video",
    "kling-pro": "fal-ai/kling-video/v3/pro/image-to-video",
}


class FalKlingProvider(VideoProvider):
    """fal.ai Kling image-to-video (replacement for shutdown Sora Videos API)."""

    name = "fal"

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("FAL_KEY is required for the fal / anthropic video pipeline")
        self.api_key = api_key
        self._meta_by_job: dict[str, dict] = {}

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Key {self.api_key}",
            "Content-Type": "application/json",
        }

    def _model_id(self, model: str) -> str:
        return FAL_MODELS.get(model, FAL_MODELS["sora-2"])

    def _duration(self, seconds: str, model: str) -> str:
        try:
            n = int(seconds)
        except ValueError:
            n = 10
        mid = self._model_id(model)
        if "v2.5" in mid:
            return "10" if n >= 8 else "5"
        return str(max(3, min(15, n)))

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
        model_id = self._model_id(model)
        image_url = _as_data_uri(image_path)
        body_input: dict = {
            "prompt": prompt,
            "duration": self._duration(seconds, model),
            "negative_prompt": (
                "blur, distort, low quality, identity change, morphing face, "
                "text overlay, watermark, multiple people, camera shake"
            ),
            "cfg_scale": 0.5,
        }
        if "v3" in model_id:
            body_input["start_image_url"] = image_url
            body_input["generate_audio"] = False
        else:
            body_input["image_url"] = image_url

        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                f"https://queue.fal.run/{model_id}",
                headers=self._headers(),
                json=body_input,
            )
            if resp.status_code >= 400:
                return ProviderResult(
                    status="failed",
                    message="Kling rejected the request",
                    error=_extract_error(resp),
                )
            body = resp.json()
            request_id = body.get("request_id") or body.get("requestId") or ""
            meta = {
                "request_id": request_id,
                "model_id": model_id,
                "status_url": body.get("status_url")
                or f"https://queue.fal.run/{model_id}/requests/{request_id}/status",
                "response_url": body.get("response_url")
                or f"https://queue.fal.run/{model_id}/requests/{request_id}",
            }
            self._meta_by_job[request_id] = meta
            return ProviderResult(
                status="processing",
                message="Job queued · waiting for Kling…",
                progress=5.0,
                provider_job_id=request_id,
            )

    async def poll(self, *, provider_job_id: str, out_dir: Path) -> ProviderResult:
        meta = self._meta_by_job.get(provider_job_id)
        if not meta:
            # Reconstruct URLs using default model if meta was lost (process restart)
            model_id = FAL_MODELS["sora-2"]
            meta = {
                "request_id": provider_job_id,
                "status_url": f"https://queue.fal.run/{model_id}/requests/{provider_job_id}/status",
                "response_url": f"https://queue.fal.run/{model_id}/requests/{provider_job_id}",
            }

        async with httpx.AsyncClient(timeout=120.0) as client:
            status_resp = await client.get(meta["status_url"], headers=self._headers())
            if status_resp.status_code >= 400:
                return ProviderResult(
                    status="failed",
                    message="Failed to poll Kling",
                    error=_extract_error(status_resp),
                    provider_job_id=provider_job_id,
                )
            status_body = status_resp.json()
            st = (status_body.get("status") or "").upper()
            if st in {"IN_QUEUE", "IN_PROGRESS"}:
                return ProviderResult(
                    status="processing",
                    message=(
                        "Generating with Kling…"
                        if st == "IN_PROGRESS"
                        else "Job queued · waiting for Kling…"
                    ),
                    progress=40.0 if st == "IN_PROGRESS" else 15.0,
                    provider_job_id=provider_job_id,
                )
            if st in {"FAILED", "CANCELLED", "ERROR"}:
                return ProviderResult(
                    status="failed",
                    message="Kling couldn't produce the verification clip.",
                    error=str(status_body.get("error") or status_body)[:400],
                    provider_job_id=provider_job_id,
                )

            result_resp = await client.get(meta["response_url"], headers=self._headers())
            if result_resp.status_code >= 400:
                return ProviderResult(
                    status="failed",
                    message="Failed to fetch Kling result",
                    error=_extract_error(result_resp),
                    provider_job_id=provider_job_id,
                )
            data = result_resp.json()
            video = data.get("video") or (data.get("data") or {}).get("video") or {}
            url = video.get("url") if isinstance(video, dict) else None
            if not url:
                return ProviderResult(
                    status="failed",
                    message="Kling returned no video URL",
                    error=str(data)[:400],
                    provider_job_id=provider_job_id,
                )
            out_dir.mkdir(parents=True, exist_ok=True)
            video_path = out_dir / "verification.mp4"
            dl = await client.get(url, timeout=180.0)
            dl.raise_for_status()
            video_path.write_bytes(dl.content)
            return ProviderResult(
                status="completed",
                message="Verification video ready",
                progress=100.0,
                video_path=video_path,
                provider_job_id=provider_job_id,
            )


def _as_data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _extract_error(resp: httpx.Response) -> str:
    try:
        data = resp.json()
        if isinstance(data, dict):
            detail = data.get("detail") or data.get("error") or data.get("message")
            if isinstance(detail, dict):
                return str(detail.get("message") or detail)
            if detail:
                return str(detail)
        return str(data)[:400]
    except Exception:
        return resp.text[:400] or f"HTTP {resp.status_code}"
