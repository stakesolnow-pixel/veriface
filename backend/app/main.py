from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import aiofiles
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .config import get_settings
from .jobs import JobStatus, store
from .prompt import LIVENESS_PROMPT
from .providers import get_provider

logger = logging.getLogger("veriface")
logging.basicConfig(level=logging.INFO)

ALLOWED_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
ALLOWED_MODELS = {"sora-2", "sora-2-pro"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "jobs").mkdir(parents=True, exist_ok=True)
    app.state.settings = settings
    try:
        app.state.provider = get_provider(settings)
    except Exception as exc:
        logger.error("Provider init failed: %s", exc)
        app.state.provider = None
        app.state.provider_error = str(exc)
    else:
        app.state.provider_error = None
    logger.info(
        "Veriface API ready · provider=%s",
        getattr(app.state.provider, "name", "unavailable"),
    )
    purge_task = asyncio.create_task(_purge_loop())
    yield
    purge_task.cancel()


app = FastAPI(title="Veriface API", version="1.0.0", lifespan=lifespan)

settings_boot = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings_boot.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _purge_loop() -> None:
    while True:
        try:
            await store.purge_expired(get_settings().job_ttl_seconds)
        except Exception:
            logger.exception("purge failed")
        await asyncio.sleep(300)


@app.get("/api/")
async def api_root():
    provider = getattr(app.state, "provider", None)
    return {
        "message": "Veriface API",
        "status": "ok",
        "provider": getattr(provider, "name", None),
        "standalone": True,
    }


@app.get("/api/health")
async def health():
    provider = getattr(app.state, "provider", None)
    return {
        "status": "ok" if provider else "degraded",
        "provider": getattr(provider, "name", None),
        "error": getattr(app.state, "provider_error", None),
    }


@app.post("/api/verify/start")
async def verify_start(
    image: UploadFile = File(...),
    model: str = Form("sora-2"),
):
    settings = app.state.settings
    provider = app.state.provider
    if provider is None:
        raise HTTPException(status_code=503, detail=app.state.provider_error or "Provider unavailable")

    model = (model or settings.default_model).strip()
    if model not in ALLOWED_MODELS:
        raise HTTPException(status_code=400, detail=f"Unsupported model. Use one of: {', '.join(sorted(ALLOWED_MODELS))}")

    content_type = (image.content_type or "").lower()
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file. Please upload a JPEG, PNG, or WEBP image.")

    raw = await image.read()
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(status_code=400, detail="Image too large. Max 12MB.")
    if not raw:
        raise HTTPException(status_code=400, detail="Empty upload.")

    job = await store.create(model=model)
    job_dir = settings.data_dir / "jobs" / job.id
    job_dir.mkdir(parents=True, exist_ok=True)

    ext = _ext_for(content_type, image.filename)
    image_path = job_dir / f"input{ext}"
    async with aiofiles.open(image_path, "wb") as fh:
        await fh.write(raw)

    await store.update(
        job.id,
        image_path=image_path,
        status=JobStatus.uploading,
        message="Uploading photo…",
    )

    asyncio.create_task(_run_job(job.id))
    return {"job_id": job.id, "status": "queued"}


@app.get("/api/verify/status/{job_id}")
async def verify_status(job_id: str):
    job = await store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_status()


@app.get("/api/verify/download/{job_id}")
async def verify_download(job_id: str):
    job = await store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.completed or not job.video_path or not Path(job.video_path).exists():
        raise HTTPException(status_code=409, detail="Video not ready")
    return FileResponse(
        path=str(job.video_path),
        media_type="video/mp4",
        filename=f"verification_{job_id}.mp4",
    )


async def _run_job(job_id: str) -> None:
    settings = app.state.settings
    provider = app.state.provider
    job = await store.get(job_id)
    if not job or not job.image_path:
        return

    job_dir = settings.data_dir / "jobs" / job_id
    try:
        await store.update(
            job_id,
            status=JobStatus.processing,
            message="Job queued · waiting for video provider…",
            progress=5.0,
        )
        result = await provider.start(
            image_path=Path(job.image_path),
            model=job.model,
            prompt=LIVENESS_PROMPT,
            seconds=settings.video_seconds,
            size=settings.video_size,
            out_dir=job_dir,
        )

        if result.status == "failed":
            await store.update(
                job_id,
                status=JobStatus.failed,
                message=result.message,
                error=result.error or result.message,
                progress=result.progress,
                provider_job_id=result.provider_job_id,
            )
            return

        if result.status == "completed" and result.video_path:
            await store.update(
                job_id,
                status=JobStatus.completed,
                message=result.message,
                progress=100.0,
                video_path=result.video_path,
                provider_job_id=result.provider_job_id,
            )
            return

        # Async provider — poll until done
        provider_job_id = result.provider_job_id
        await store.update(
            job_id,
            status=JobStatus.processing,
            message=result.message,
            progress=result.progress or 10.0,
            provider_job_id=provider_job_id,
        )

        while True:
            await asyncio.sleep(settings.poll_interval_seconds)
            polled = await provider.poll(provider_job_id=provider_job_id, out_dir=job_dir)
            if polled.status == "completed" and polled.video_path:
                await store.update(
                    job_id,
                    status=JobStatus.completed,
                    message=polled.message,
                    progress=100.0,
                    video_path=polled.video_path,
                )
                return
            if polled.status == "failed":
                await store.update(
                    job_id,
                    status=JobStatus.failed,
                    message=polled.message,
                    error=polled.error or polled.message,
                    progress=polled.progress,
                )
                return
            await store.update(
                job_id,
                status=JobStatus.processing,
                message=polled.message,
                progress=polled.progress,
            )
    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        await store.update(
            job_id,
            status=JobStatus.failed,
            message="Generation failed",
            error=str(exc),
        )


def _ext_for(content_type: str, filename: str | None) -> str:
    if content_type in {"image/jpeg", "image/jpg"}:
        return ".jpg"
    if content_type == "image/png":
        return ".png"
    if content_type == "image/webp":
        return ".webp"
    if filename and "." in filename:
        return "." + filename.rsplit(".", 1)[-1].lower()
    return ".jpg"


@app.exception_handler(Exception)
async def unhandled(_, exc: Exception):
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
