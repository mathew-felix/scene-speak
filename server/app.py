from __future__ import annotations

import logging
import queue
import shutil
import threading
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from config import OUTPUT_DIR, PORT
from pipeline.image_normalize import normalize_image_path
from pipeline.kokoro_tts import synthesize_wav
from pipeline.openai_story import StoryError, elaborate_story
from pipeline.qwen import VisionError, describe_scene, stop_server

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("scenespeak")

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
JOB_TTL_SECONDS = 60 * 60


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    stop_server()  # uvicorn re-raises SIGTERM, so atexit alone would leave llama-server running


app = FastAPI(title="SceneSpeak API", version="1.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Stage(str, Enum):
    QUEUED = "queued"
    QWEN = "qwen"
    OPENAI = "openai"
    TTS = "tts"
    DONE = "done"
    ERROR = "error"


STAGE_PROGRESS: dict[Stage, int] = {
    Stage.QUEUED: 5,
    Stage.QWEN: 15,
    Stage.OPENAI: 60,
    Stage.TTS: 78,
    Stage.DONE: 100,
    Stage.ERROR: 100,
}


@dataclass
class Job:
    id: str
    stage: Stage = Stage.QUEUED
    progress: int = STAGE_PROGRESS[Stage.QUEUED]
    caption: str | None = None
    scene_context: str | None = None
    story: str | None = None
    audio_path: str | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def to_dict(self) -> dict[str, Any]:
        with self.lock:
            return {
                "jobId": self.id,
                "stage": self.stage.value,
                "progress": self.progress,
                "caption": self.caption,
                "sceneContext": self.scene_context,
                "story": self.story,
                "audioUrl": f"/v1/jobs/{self.id}/audio" if self.audio_path else None,
                "error": self.error,
            }


jobs: dict[str, Job] = {}
jobs_lock = threading.Lock()
work_queue: "queue.Queue[tuple[str, Path]]" = queue.Queue()


def set_stage(job: Job, stage: Stage) -> None:
    with job.lock:
        job.stage = stage
        job.progress = STAGE_PROGRESS[stage]


def fail_job(job: Job, message: str) -> None:
    with job.lock:
        job.stage = Stage.ERROR
        job.progress = STAGE_PROGRESS[Stage.ERROR]
        job.error = message


def run_pipeline(job_id: str, image_path: Path) -> None:
    job = jobs[job_id]
    started = time.time()
    try:
        image_path = normalize_image_path(image_path)

        set_stage(job, Stage.QWEN)
        caption, scene_context = describe_scene(str(image_path))
        with job.lock:
            job.caption = caption
            job.scene_context = scene_context
        logger.info("[%s] caption: %s", job_id, caption)
        logger.info("[%s] qwen inventory:\n%s", job_id, scene_context)

        set_stage(job, Stage.OPENAI)
        story = elaborate_story(scene_context)
        with job.lock:
            job.story = story
        logger.info("[%s] story: %d chars", job_id, len(story))

        set_stage(job, Stage.TTS)
        wav_path = synthesize_wav(story, job_id)
        with job.lock:
            job.audio_path = str(wav_path)

        set_stage(job, Stage.DONE)
        logger.info("[%s] done in %.1fs", job_id, time.time() - started)
    except (StoryError, VisionError) as exc:
        logger.error("[%s] step failed: %s", job_id, exc)
        fail_job(job, str(exc))
    except Exception as exc:  # noqa: BLE001 - surface any failure to the client
        logger.exception("[%s] pipeline failed", job_id)
        fail_job(job, f"{type(exc).__name__}: {exc}")
    finally:
        for leftover in OUTPUT_DIR.glob(f"{job_id}-source*"):
            leftover.unlink(missing_ok=True)


def cleanup_old_jobs() -> None:
    cutoff = time.time() - JOB_TTL_SECONDS
    with jobs_lock:
        expired = [jid for jid, job in jobs.items() if job.created_at < cutoff]
        for jid in expired:
            job = jobs.pop(jid)
            if job.audio_path:
                Path(job.audio_path).unlink(missing_ok=True)


def worker_loop() -> None:
    """One job at a time so the models never compete for memory."""
    while True:
        job_id, image_path = work_queue.get()
        try:
            run_pipeline(job_id, image_path)
        finally:
            work_queue.task_done()
            cleanup_old_jobs()


threading.Thread(target=worker_loop, daemon=True, name="scene-worker").start()


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "queued": work_queue.qsize()}


@app.post("/v1/scenes/process")
async def process_scene(image: UploadFile = File(...)) -> dict[str, str]:
    if image.content_type and not image.content_type.startswith(("image/", "application/octet-stream")):
        raise HTTPException(status_code=400, detail="Expected an image upload")

    job_id = uuid.uuid4().hex
    suffix = Path(image.filename or "photo.jpg").suffix or ".jpg"
    temp_path = OUTPUT_DIR / f"{job_id}-source{suffix}"

    written = 0
    with temp_path.open("wb") as out:
        while chunk := await image.read(1024 * 1024):
            written += len(chunk)
            if written > MAX_UPLOAD_BYTES:
                out.close()
                temp_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Image is too large (max 25 MB)")
            out.write(chunk)

    if written == 0:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Empty upload")

    with jobs_lock:
        jobs[job_id] = Job(id=job_id)
    work_queue.put((job_id, temp_path))
    return {"jobId": job_id}


@app.get("/v1/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()


@app.get("/v1/jobs/{job_id}/audio")
def get_audio(job_id: str) -> FileResponse:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.audio_path or not Path(job.audio_path).is_file():
        raise HTTPException(status_code=404, detail="Audio not ready")
    return FileResponse(job.audio_path, media_type="audio/wav", filename=f"{job_id}.wav")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
