"""Turns whatever the phone uploads (HEIC, PNG, rotated JPEG...) into a clean upright RGB JPEG."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from PIL import Image, ImageOps

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:  # pragma: no cover - HEIC then relies on the sips fallback
    pillow_heif = None

logger = logging.getLogger("scenespeak.image")

MAX_SIDE = 1280


def _save_normalized(src: Path, out: Path) -> None:
    with Image.open(src) as image:
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")
        image.thumbnail((MAX_SIDE, MAX_SIDE))
        image.save(out, "JPEG", quality=88)


def normalize_image_path(src: Path) -> Path:
    """Returns the path of a normalized JPEG next to `src`. Raises ValueError for unreadable files."""
    out = src.with_name(f"{src.stem}-norm.jpg")
    try:
        _save_normalized(src, out)
        return out
    except Exception as first_error:  # noqa: BLE001
        logger.warning("Pillow could not read %s (%s); trying sips", src.name, first_error)

    converted = src.with_name(f"{src.stem}-sips.jpg")
    try:
        subprocess.run(
            ["sips", "-s", "format", "jpeg", str(src), "--out", str(converted)],
            check=True,
            capture_output=True,
            timeout=60,
        )
        _save_normalized(converted, out)
        return out
    except Exception as exc:  # noqa: BLE001
        raise ValueError("This file is not an image the server can read") from exc
    finally:
        converted.unlink(missing_ok=True)
