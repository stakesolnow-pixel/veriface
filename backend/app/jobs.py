from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class JobStatus(str, Enum):
    queued = "queued"
    uploading = "uploading"
    processing = "processing"
    completed = "completed"
    failed = "failed"


@dataclass
class Job:
    id: str
    model: str
    status: JobStatus = JobStatus.queued
    message: str = "Job queued · waiting for video provider…"
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    image_path: Path | None = None
    video_path: Path | None = None
    provider_job_id: str | None = None
    progress: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.updated_at = time.time()

    def to_status(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "job_id": self.id,
            "status": self.status.value,
            "message": self.message,
            "progress": self.progress,
            "model": self.model,
        }
        if self.error:
            payload["error"] = self.error
        return payload


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = asyncio.Lock()

    async def create(self, model: str) -> Job:
        job = Job(id=str(uuid.uuid4()), model=model)
        async with self._lock:
            self._jobs[job.id] = job
        return job

    async def get(self, job_id: str) -> Job | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def update(self, job_id: str, **kwargs: Any) -> Job | None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            for key, value in kwargs.items():
                setattr(job, key, value)
            job.touch()
            return job

    async def purge_expired(self, ttl_seconds: int) -> None:
        cutoff = time.time() - ttl_seconds
        async with self._lock:
            expired = [jid for jid, job in self._jobs.items() if job.created_at < cutoff]
            for jid in expired:
                job = self._jobs.pop(jid)
                for path in (job.image_path, job.video_path):
                    if path and path.exists():
                        try:
                            path.unlink()
                        except OSError:
                            pass


store = JobStore()
