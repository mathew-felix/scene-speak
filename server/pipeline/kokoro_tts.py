"""Kokoro text-to-speech (multi-lang v1.0) through sherpa-onnx. Pinned to 1.12.x: 2.x drops words."""

from __future__ import annotations

import logging
import re
import threading
from functools import lru_cache
from pathlib import Path

import sherpa_onnx
import soundfile as sf

from config import KOKORO_DIR, OUTPUT_DIR

logger = logging.getLogger("scenespeak.tts")

SPEAKER_ID = 3  # voice number inside voices.bin: "af_heart" (American English, female)
SPEED = 1.0  # 1.0 = normal speaking rate

# Guards the one-time model load so two threads cannot build the engine at the same moment.
_init_lock = threading.Lock()


def clean_text_for_tts(text: str) -> str:
    """Strip markdown and stray symbols; returns "" when nothing speakable is left."""
    # Symbols like * _ ` # > would be read aloud or cause odd pauses, so replace them with spaces.
    text = re.sub(r"[*_`#>]+", " ", text)
    # Collapse repeated whitespace/newlines into single spaces.
    text = re.sub(r"\s+", " ", text).strip()
    # If no letter or digit remains, there is nothing to say.
    return text if re.search(r"[A-Za-z0-9]", text) else ""


@lru_cache(maxsize=1)  # build the engine once and reuse it: loading the model is slow
def _tts() -> sherpa_onnx.OfflineTts:
    """Create the Kokoro engine from the model files in KOKORO_DIR (offline, CPU only)."""
    if not (KOKORO_DIR / "model.onnx").is_file():
        raise FileNotFoundError(f"Missing Kokoro model in {KOKORO_DIR}")
    # model.onnx = the neural network, voices.bin = the speaker voice styles,
    # tokens.txt = the symbol table, lexicon = word -> pronunciation dictionaries.
    kokoro = sherpa_onnx.OfflineTtsKokoroModelConfig(
        model=str(KOKORO_DIR / "model.onnx"),
        voices=str(KOKORO_DIR / "voices.bin"),
        tokens=str(KOKORO_DIR / "tokens.txt"),
        lexicon=f"{KOKORO_DIR / 'lexicon-us-en.txt'},{KOKORO_DIR / 'lexicon-zh.txt'}",
        # espeak-ng data: rules for pronouncing words that are not in the lexicon.
        data_dir=str(KOKORO_DIR / "espeak-ng-data"),
        dict_dir=str(KOKORO_DIR / "dict"),
    )
    config = sherpa_onnx.OfflineTtsConfig(
        model=sherpa_onnx.OfflineTtsModelConfig(kokoro=kokoro, num_threads=4, debug=False, provider="cpu"),
        # Text-normalization rules (dates, numbers, phone numbers) for Chinese text.
        rule_fsts=",".join(str(KOKORO_DIR / name) for name in ("date-zh.fst", "number-zh.fst", "phone-zh.fst")),
        max_num_sentences=1,
    )
    # validate() checks that every referenced file exists and is readable.
    if not config.validate():
        raise RuntimeError("Invalid Kokoro configuration")
    return sherpa_onnx.OfflineTts(config)


def synthesize_wav(text: str, job_id: str) -> Path:
    """Convert narration text to speech and save it as outputs/<job_id>.wav. Returns that path."""
    cleaned = clean_text_for_tts(text)
    if not cleaned:
        raise ValueError("There was no speakable text to convert to audio")
    # Take the lock only while the engine is created/fetched; generation itself runs outside it.
    with _init_lock:
        tts = _tts()
    audio = tts.generate(cleaned, sid=SPEAKER_ID, speed=SPEED)
    if not len(audio.samples):
        raise RuntimeError("Kokoro produced no audio")
    out = OUTPUT_DIR / f"{job_id}.wav"
    # audio.samples is a float array; soundfile writes it as a WAV at the model's sample rate.
    sf.write(str(out), audio.samples, audio.sample_rate)
    logger.info("[%s] wrote %.1fs of audio", job_id, len(audio.samples) / audio.sample_rate)
    return out
