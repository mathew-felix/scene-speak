"""SceneSpeak API server.

What this server does
---------------------
The mobile app uploads a photo and gets back a job id. The server then turns
that photo into spoken audio in four steps, one job at a time:

    photo -> normalize -> Qwen vision (what is in the picture)
          -> OpenAI (write a faithful narration) -> Kokoro (text to speech) -> WAV

The app does not wait on one long request. It polls GET /v1/jobs/{id} to see
the current stage and progress, and downloads the audio when the stage is "done".

Endpoints
---------
GET  /health                 liveness check, also reports how many jobs are waiting
POST /v1/scenes/process      upload an image (multipart field "image"), returns {"jobId"}
GET  /v1/jobs/{id}           job status: stage, progress, caption, story, audioUrl, error
GET  /v1/jobs/{id}/audio     the generated WAV file
"""

from __future__ import annotations

import logging
import queue
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

# Reject uploads above this size so a huge file cannot fill the disk or memory.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
# Finished jobs (and their audio files) are deleted after one hour.
JOB_TTL_SECONDS = 60 * 60


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Code before `yield` runs at startup (nothing to do), code after runs at shutdown.
    yield
    # The vision model runs as a separate llama-server process. Stop it when the API
    # stops, otherwise it would keep running and holding memory. We do this here
    # because uvicorn re-raises SIGTERM, so an `atexit` hook alone would never run.
    stop_server()


app = FastAPI(title="SceneSpeak API", version="1.2.0", lifespan=lifespan)

# Allow any origin. The server only listens for local development, and this lets a
# web build of the app talk to it too. Tighten this before exposing it publicly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Stage(str, Enum):
    """The steps a job moves through, in order. The app shows these to the user."""

    QUEUED = "queued"  # waiting for its turn
    QWEN = "qwen"  # the vision model is looking at the photo
    OPENAI = "openai"  # the language model is writing the narration
    TTS = "tts"  # Kokoro is turning the narration into audio
    DONE = "done"  # audio is ready
    ERROR = "error"  # something failed; see Job.error


# Progress shown in the app's progress bar. The numbers are roughly how far along
# each step is, not exact percentages. Each value is set when that stage *starts*.
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
    """Everything the server knows about one photo being processed."""

    id: str
    stage: Stage = Stage.QUEUED
    progress: int = STAGE_PROGRESS[Stage.QUEUED]
    caption: str | None = None  # one-line summary of the photo
    scene_context: str | None = None  # the detailed inventory from the vision model
    story: str | None = None  # the final narration text
    audio_path: str | None = None  # path of the generated WAV on disk
    error: str | None = None  # user-facing message when stage is ERROR
    created_at: float = field(default_factory=time.time)
    # The worker thread writes to the job while request threads read it, so every
    # read or write of the fields above happens while holding this lock.
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def to_dict(self) -> dict[str, Any]:
        """The JSON the app receives when it polls. Field names match the app's types."""
        with self.lock:
            return {
                "jobId": self.id,
                "stage": self.stage.value,
                "progress": self.progress,
                "caption": self.caption,
                "sceneContext": self.scene_context,
                "story": self.story,
                # Only give a download link once the audio file actually exists.
                "audioUrl": f"/v1/jobs/{self.id}/audio" if self.audio_path else None,
                "error": self.error,
            }


# In-memory job store. Jobs are lost if the server restarts, which is fine because
# the app saves finished scenes on the device.
jobs: dict[str, Job] = {}
jobs_lock = threading.Lock()  # protects adding and removing entries in `jobs`
# Waiting jobs as (job id, path of the uploaded image). The worker thread reads this.
work_queue: "queue.Queue[tuple[str, Path]]" = queue.Queue()


def set_stage(job: Job, stage: Stage) -> None:
    """Move a job to a new stage and update its progress to match."""
    with job.lock:
        job.stage = stage
        job.progress = STAGE_PROGRESS[stage]


def fail_job(job: Job, message: str) -> None:
    """Mark a job as failed. The app shows `message` to the user and drops the photo."""
    with job.lock:
        job.stage = Stage.ERROR
        job.progress = STAGE_PROGRESS[Stage.ERROR]
        job.error = message


def run_pipeline(job_id: str, image_path: Path) -> None:
    """Run all four steps for one job. Runs on the worker thread, never on a request.

    Any failure is caught and stored on the job instead of being raised, so one bad
    photo can never crash the worker or block the jobs behind it.
    """
    job = jobs[job_id]
    started = time.time()
    try:
        # Step 1: fix orientation, shrink large photos and convert to a plain JPEG
        # (phones often send HEIC). This also makes the vision step faster.
        image_path = normalize_image_path(image_path)

        # Step 2: the vision model lists what it sees (objects, colors, positions,
        # people, animals, text). It does not write prose.
        set_stage(job, Stage.QWEN)
        caption, scene_context = describe_scene(str(image_path))
        with job.lock:
            job.caption = caption
            job.scene_context = scene_context
        logger.info("[%s] caption: %s", job_id, caption)
        logger.info("[%s] qwen inventory:\n%s", job_id, scene_context)

        # Step 3: the language model turns that inventory into a flowing narration.
        # It only receives text, so the photo itself never leaves this machine.
        set_stage(job, Stage.OPENAI)
        story = elaborate_story(scene_context)
        with job.lock:
            job.story = story
        logger.info("[%s] story: %d chars", job_id, len(story))

        # Step 4: Kokoro reads the narration aloud and writes a WAV file.
        set_stage(job, Stage.TTS)
        wav_path = synthesize_wav(story, job_id)
        with job.lock:
            job.audio_path = str(wav_path)

        set_stage(job, Stage.DONE)
        logger.info("[%s] done in %.1fs", job_id, time.time() - started)
    except (StoryError, VisionError) as exc:
        # Expected failures (missing API key, rate limit, model not responding...).
        # These messages are written to be read by the user, so pass them through.
        logger.error("[%s] step failed: %s", job_id, exc)
        fail_job(job, str(exc))
    except Exception as exc:  # noqa: BLE001 - surface any failure to the client
        # Anything unexpected: log the full traceback for us, give the app a short message.
        logger.exception("[%s] pipeline failed", job_id)
        fail_job(job, f"{type(exc).__name__}: {exc}")
    finally:
        # Always delete the uploaded photo and its normalized copy, success or not.
        for leftover in OUTPUT_DIR.glob(f"{job_id}-source*"):
            leftover.unlink(missing_ok=True)


def cleanup_old_jobs() -> None:
    """Forget jobs older than JOB_TTL_SECONDS and delete their audio files."""
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
        # Blocks here until a job is queued.
        job_id, image_path = work_queue.get()
        try:
            run_pipeline(job_id, image_path)
        finally:
            work_queue.task_done()
            # Tidy up after every job, so no separate cleanup timer is needed.
            cleanup_old_jobs()


# Start the single worker. `daemon=True` means it will not keep the process alive
# on shutdown. Because there is exactly one worker, jobs run strictly in upload order.
threading.Thread(target=worker_loop, daemon=True, name="scene-worker").start()


@app.get("/health")
def health() -> dict[str, Any]:
    """Quick check that the server is up. `queued` is the number of jobs waiting."""
    return {"status": "ok", "queued": work_queue.qsize()}


@app.post("/v1/scenes/process")
async def process_scene(image: UploadFile = File(...)) -> dict[str, str]:
    """Accept a photo, queue it for processing and return a job id right away.

    The heavy work happens later on the worker thread, so this returns in milliseconds.
    """
    # Some clients send no content type, or a generic one, so only reject types that
    # are clearly not images.
    if image.content_type and not image.content_type.startswith(("image/", "application/octet-stream")):
        raise HTTPException(status_code=400, detail="Expected an image upload")

    job_id = uuid.uuid4().hex
    # Keep the original extension (.jpg, .heic...) so the image library can detect the format.
    suffix = Path(image.filename or "photo.jpg").suffix or ".jpg"
    temp_path = OUTPUT_DIR / f"{job_id}-source{suffix}"

    # Save the upload in 1 MB pieces instead of reading it all into memory, and stop
    # as soon as it passes the size limit.
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

    # Register the job first, then queue it, so the worker always finds it in `jobs`.
    with jobs_lock:
        jobs[job_id] = Job(id=job_id)
    work_queue.put((job_id, temp_path))
    return {"jobId": job_id}


@app.get("/v1/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    """Current state of a job. The app calls this about once a second until done or error."""
    job = jobs.get(job_id)
    if not job:
        # Unknown id, or the job expired after JOB_TTL_SECONDS.
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()


@app.get("/v1/jobs/{job_id}/audio")
def get_audio(job_id: str) -> FileResponse:
    """Download the finished WAV. Returns 404 if the job is unknown or audio is not ready."""
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.audio_path or not Path(job.audio_path).is_file():
        raise HTTPException(status_code=404, detail="Audio not ready")
    return FileResponse(job.audio_path, media_type="audio/wav", filename=f"{job_id}.wav")


if __name__ == "__main__":
    # Allows `python app.py`. The normal way to start the server is `npm run server`
    # or ./scripts/run.sh. Host 0.0.0.0 makes it reachable from other devices too.
    uvicorn.run(app, host="0.0.0.0", port=PORT)
