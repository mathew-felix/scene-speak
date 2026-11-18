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

STARTUP_TIMEOUT_SECONDS = 240
REQUEST_TIMEOUT_SECONDS = 300

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

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

_proc: subprocess.Popen | None = None
_proc_lock = threading.Lock()


class VisionError(RuntimeError):
    """User-facing failure in the image-understanding step."""


def clean_model_text(text: str) -> str:
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
    seen: set[str] = set()
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip(" -\t")
        if not line:
            continue
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        lines.append(line)
    return "\n".join(lines)[:2000]


def caption_from_inventory(inventory: str) -> str:
    for line in inventory.splitlines():
        if line.lower().startswith("setting:"):
            value = line.split(":", 1)[1].strip().rstrip(".")
            if value:
                return value[0].upper() + value[1:]
    first = inventory.splitlines()[0] if inventory else ""
    return first.split(".")[0].strip() or "Scene"


# --- llama-server process management -------------------------------------------------------------


def _base_url() -> str:
    return f"http://127.0.0.1:{LLAMA_SERVER_PORT}"


def _is_healthy() -> bool:
    try:
        with urllib.request.urlopen(f"{_base_url()}/health", timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def _find_binary() -> str:
    candidate = os.getenv("LLAMA_SERVER_BIN") or shutil.which("llama-server") or "/opt/homebrew/bin/llama-server"
    if not candidate or not os.path.exists(candidate):
        raise VisionError('llama.cpp is not installed. Run "brew install llama.cpp" on the Mac.')
    return candidate


def stop_server() -> None:
    """Terminate the managed llama-server child process, if any."""
    global _proc
    if _proc and _proc.poll() is None:
        _proc.terminate()
        try:
            _proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _proc.kill()
    _proc = None


atexit.register(stop_server)


def ensure_server() -> None:
    """Start llama-server if it is not already answering. Safe to call from any thread."""
    global _proc
    with _proc_lock:
        if _is_healthy():
            return
        for path in (QWEN_GGUF, MMPROJ_GGUF):
            if not path.is_file():
                raise VisionError(f"Missing model file: {path}")

        stop_server()
        binary = _find_binary()
        log_path = OUTPUT_DIR / "llama-server.log"
        logger.info("Starting llama-server (Qwen3.5-2B vision) on port %s", LLAMA_SERVER_PORT)
        log_file = log_path.open("ab")
        _proc = subprocess.Popen(
            [
                binary,
                "-m", str(QWEN_GGUF),
                "--mmproj", str(MMPROJ_GGUF),
                "--host", "127.0.0.1",
                "--port", str(LLAMA_SERVER_PORT),
                "-c", "4096",
                "-ngl", "99",
                "--chat-template-kwargs", json.dumps({"enable_thinking": False}),
                "--no-webui",
            ],
            stdout=log_file,
            stderr=log_file,
        )

        deadline = time.time() + STARTUP_TIMEOUT_SECONDS
        while time.time() < deadline:
            if _proc.poll() is not None:
                raise VisionError(f"The Qwen vision server exited during start-up. See {log_path}")
            if _is_healthy():
                logger.info("llama-server ready")
                return
            time.sleep(1)
        stop_server()
        raise VisionError("The Qwen vision server took too long to start")


def _post_chat(image_b64: str) -> str:
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
        "temperature": 0.1,
        "top_p": 0.8,
        "repeat_penalty": 1.15,
        "max_tokens": 450,
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
    for attempt in range(2):
        ensure_server()
        try:
            raw = _post_chat(image_b64)
            break
        except (urllib.error.URLError, OSError, KeyError, ValueError) as exc:
            last_error = exc
            logger.warning("Qwen request failed (attempt %s): %s", attempt + 1, exc)
            with _proc_lock:
                if not _is_healthy():
                    stop_server()
    else:
        raise VisionError(f"The Qwen vision step failed: {last_error}")

    inventory = clean_inventory(raw)
    if not inventory:
        raise VisionError("Qwen could not describe this image. Try another photo.")
    return caption_from_inventory(inventory), inventory
