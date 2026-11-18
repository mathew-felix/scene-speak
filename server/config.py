from pathlib import Path

from dotenv import load_dotenv
import os

ROOT = Path(__file__).resolve().parents[1]
SERVER_DIR = Path(__file__).resolve().parent
MODELS = ROOT / "models"

load_dotenv(SERVER_DIR / ".env")

# Qwen3.5-2B vision model plus its vision encoder ("mmproj").
QWEN_GGUF = MODELS / "Qwen3.5-2B-Q4_K_M.gguf"
MMPROJ_GGUF = MODELS / "mmproj-F16.gguf"
KOKORO_DIR = MODELS / "kokoro-multi-lang-v1_0"
LLAMA_SERVER_PORT = int(os.getenv("LLAMA_SERVER_PORT", "8788"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
PORT = int(os.getenv("SCENE_SPEAK_PORT", "8787"))

OUTPUT_DIR = SERVER_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
