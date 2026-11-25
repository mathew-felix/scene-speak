"""Qwen3.5 vision step: looks at the photo and lists what is visible.

Qwen3.5-2B is natively multimodal, but the vision encoder lives in a separate `mmproj` file.
llama-cpp-python cannot run it yet, so we run Homebrew's `llama-server` (llama.cpp) as a managed
child process and talk to it over its OpenAI-compatible HTTP API. The model stays loaded between
photos, so only the first photo pays the start-up cost.
"""

from __future__ import annotations

import atexit
import base64
import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request

from config import LLAMA_SERVER_PORT, MMPROJ_GGUF, OUTPUT_DIR, QWEN_GGUF

logger = logging.getLogger("scenespeak.qwen")

STARTUP_TIMEOUT_SECONDS = 240  # first start loads the model into memory, which can be slow
REQUEST_TIMEOUT_SECONDS = 300  # max wait for one image to be analysed

# The prompt forces a fixed seven-line format so the output is easy to clean, easy to parse
# (the "Setting:" line becomes the caption) and easy for the narration step to consume.
INVENTORY_PROMPT = (
    "You are the eyes for a blind person. Report only what you can clearly see.\n"
    "Reply with exactly these seven labelled lines, in this order, and then stop. "
    "Write the answer after each label; do not use brackets or angle signs.\n\n"
    "Setting: the type of place or scene, plus lighting or weather only if obvious.\n"
    "Main subject: the single most important thing, with its colors and where it is.\n"
    "Objects: other objects, each with colors, relative size (small, medium or large) and its OWN position.\n"
    "People: for each person the apparent age group, clothing with colors, pose or action, position and "
    "which way they face, or none visible.\n"
    "Animals and insects: for each the kind, colors, action and position, or none visible.\n"
    "Text and signs: any readable text copied exactly, or none visible.\n"
    "Background: sky, ground, distant things and where they are.\n\n"
    "Positions use: left, center, right, top, middle, bottom, foreground, background.\n"
    "Write short plain phrases. Never give measurements in centimeters, meters or inches. "
    "Never guess, never mention feelings, never name species or brands unless clearly readable. "
    "Never repeat an item."
)

# Some Qwen models print their reasoning inside <think>...</think>. We never want that text.
_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

# The llama-server child process (None until started) and a lock so that two threads
# cannot start or stop it at the same time.
_proc: subprocess.Popen | None = None
_proc_lock = threading.Lock()


class VisionError(RuntimeError):
    """User-facing failure in the image-understanding step."""


def clean_model_text(text: str) -> str:
    """Remove think blocks and markdown symbols from free-form model output."""
    text = _THINK_BLOCK.sub("", text)
    # Unterminated think block (generation cut off mid-thought)
    if "<think>" in text.lower():
        text = text.split("<think>")[0]
    text = re.sub(r"[*_`#>]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_inventory(text: str) -> str:
    """Strip think blocks/markdown/template brackets, drop repeated lines."""
    text = _THINK_BLOCK.sub("", text)
    if "<think>" in text.lower():
        text = text.split("<think>")[0]
    text = re.sub(r"[*_`#<>]+", "", text)
    lines: list[str] = []
    seen: set[str] = set()  # lowercase lines already kept, to detect repeats
    for raw in text.splitlines():
        # Normalize spaces and trim bullet dashes/tabs at the ends.
        line = re.sub(r"\s+", " ", raw).strip(" -\t")
        if not line:
            continue
        key = line.lower()
        if key in seen:  # small models sometimes loop; keep only the first copy
            continue
        seen.add(key)
        lines.append(line)
    # Cap the length so a runaway answer cannot bloat the next step's prompt.
    return "\n".join(lines)[:2000]


def caption_from_inventory(inventory: str) -> str:
    """Pick a short caption: the 'Setting:' line if present, else the first sentence."""
    for line in inventory.splitlines():
        if line.lower().startswith("setting:"):
            value = line.split(":", 1)[1].strip().rstrip(".")
            if value:
                return value[0].upper() + value[1:]
    first = inventory.splitlines()[0] if inventory else ""
    return first.split(".")[0].strip() or "Scene"


# --- llama-server process management -------------------------------------------------------------


def _base_url() -> str:
    """Address of the local llama-server (127.0.0.1 only, so it is not reachable from the network)."""
    return f"http://127.0.0.1:{LLAMA_SERVER_PORT}"


def _is_healthy() -> bool:
    """True when llama-server answers its /health endpoint, i.e. the model is loaded and ready."""
    try:
        with urllib.request.urlopen(f"{_base_url()}/health", timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def _find_binary() -> str:
    """Locate llama-server: env override LLAMA_SERVER_BIN, then PATH, then the Homebrew default."""
    candidate = os.getenv("LLAMA_SERVER_BIN") or shutil.which("llama-server") or "/opt/homebrew/bin/llama-server"
    if not candidate or not os.path.exists(candidate):
        raise VisionError('llama.cpp is not installed. Run "brew install llama.cpp" on the Mac.')
    return candidate


def stop_server() -> None:
    """Terminate the managed llama-server child process, if any."""
    global _proc
    # poll() is None while the process is still running.
    if _proc and _proc.poll() is None:
        _proc.terminate()  # polite stop first
        try:
            _proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _proc.kill()  # force stop if it ignores the request
    _proc = None


# Make sure the child process is not left running when the API exits.
atexit.register(stop_server)


def ensure_server() -> None:
    """Start llama-server if it is not already answering. Safe to call from any thread."""
    global _proc
    with _proc_lock:
        if _is_healthy():  # already running: nothing to do
            return
        # Fail early with a clear message if the model files were not downloaded.
        for path in (QWEN_GGUF, MMPROJ_GGUF):
            if not path.is_file():
                raise VisionError(f"Missing model file: {path}")

        stop_server()  # clear any half-dead earlier process before starting a new one
        binary = _find_binary()
        # Server output goes to a log file so start-up problems can be diagnosed later.
        log_path = OUTPUT_DIR / "llama-server.log"
        logger.info("Starting llama-server (Qwen3.5-2B vision) on port %s", LLAMA_SERVER_PORT)
        log_file = log_path.open("ab")
        _proc = subprocess.Popen(
            [
                binary,
                "-m", str(QWEN_GGUF),  # the language model weights
                "--mmproj", str(MMPROJ_GGUF),  # the vision encoder that reads images
                "--host", "127.0.0.1",  # local connections only
                "--port", str(LLAMA_SERVER_PORT),
                "-c", "4096",  # context window in tokens (image + prompt + answer)
                "-ngl", "99",  # offload all layers to the GPU (Metal on a Mac)
                # Ask the chat template not to produce <think> reasoning: faster, cleaner output.
                "--chat-template-kwargs", json.dumps({"enable_thinking": False}),
                "--no-webui",  # no built-in browser UI needed
            ],
            stdout=log_file,
            stderr=log_file,
        )

        # Wait until the server reports healthy, polling once per second.
        deadline = time.time() + STARTUP_TIMEOUT_SECONDS
        while time.time() < deadline:
            if _proc.poll() is not None:  # the process died while loading
                raise VisionError(f"The Qwen vision server exited during start-up. See {log_path}")
            if _is_healthy():
                logger.info("llama-server ready")
                return
            time.sleep(1)
        stop_server()
        raise VisionError("The Qwen vision server took too long to start")


def _post_chat(image_b64: str) -> str:
    """Send one image plus INVENTORY_PROMPT to llama-server and return the raw answer text."""
    # OpenAI-compatible chat format: the image travels inline as a base64 data URL.
    body = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                    {"type": "text", "text": INVENTORY_PROMPT},
                ],
            }
        ],
        # Sampling settings tuned for factual, repeatable output rather than creativity:
        "temperature": 0.1,  # nearly deterministic
        "top_p": 0.8,  # only consider the most likely words
        "repeat_penalty": 1.15,  # discourage the looping small models tend to produce
        "max_tokens": 450,  # upper bound on the answer length
    }
    request = urllib.request.Request(
        f"{_base_url()}/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        payload = json.load(response)
    return payload["choices"][0]["message"].get("content") or ""


def describe_scene(image_path: str) -> tuple[str, str]:
    """Returns (short caption, factual inventory text) for the image."""
    with open(image_path, "rb") as handle:
        image_b64 = base64.b64encode(handle.read()).decode()

    last_error: Exception | None = None
    raw = ""
    # Up to two tries: if the first fails because the server crashed, restart it and retry once.
    for attempt in range(2):
        ensure_server()  # starts llama-server on first use; later calls return immediately
        try:
            raw = _post_chat(image_b64)
            break
        except (urllib.error.URLError, OSError, KeyError, ValueError) as exc:
            last_error = exc
            logger.warning("Qwen request failed (attempt %s): %s", attempt + 1, exc)
            with _proc_lock:
                if not _is_healthy():  # server is gone: clean up so ensure_server() restarts it
                    stop_server()
    else:  # for-else: runs only when both attempts failed (the loop never hit `break`)
        raise VisionError(f"The Qwen vision step failed: {last_error}")

    inventory = clean_inventory(raw)
    if not inventory:
        raise VisionError("Qwen could not describe this image. Try another photo.")
    return caption_from_inventory(inventory), inventory
