"""Turns whatever the phone uploads (HEIC, PNG, rotated JPEG...) into a clean upright RGB JPEG."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from PIL import Image, ImageOps

# iPhone photos are usually HEIC, which Pillow cannot open by default. pillow-heif adds a
# HEIC "opener" to Pillow. If the package is missing we do not crash: the macOS `sips`
# fallback in normalize_image_path() can still convert HEIC files.
try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:  # pragma: no cover - HEIC then relies on the sips fallback
    pillow_heif = None

logger = logging.getLogger("scenespeak.image")

# Longest allowed side in pixels. Large photos are shrunk so the vision model gets a
# smaller input (faster, less memory) while the objects stay clearly visible.
MAX_SIDE = 1280


def _save_normalized(src: Path, out: Path) -> None:
    """Open `src`, fix its orientation, convert to RGB, shrink it, and save as JPEG at `out`."""
    with Image.open(src) as image:
        # Phones store rotation in EXIF metadata instead of rotating the pixels.
        # Applying it here makes the picture upright for the model.
        image = ImageOps.exif_transpose(image)
        # JPEG has no transparency or palette, so force plain RGB (handles PNG/RGBA, etc.).
        image = image.convert("RGB")
        # thumbnail() only shrinks and keeps the aspect ratio; small images stay unchanged.
        image.thumbnail((MAX_SIDE, MAX_SIDE))
        image.save(out, "JPEG", quality=88)


def normalize_image_path(src: Path) -> Path:
    """Returns the path of a normalized JPEG next to `src`. Raises ValueError for unreadable files."""
    out = src.with_name(f"{src.stem}-norm.jpg")
    # Attempt 1: read the file directly with Pillow (covers JPEG, PNG and HEIC via pillow-heif).
    try:
        _save_normalized(src, out)
        return out
    except Exception as first_error:  # noqa: BLE001
        logger.warning("Pillow could not read %s (%s); trying sips", src.name, first_error)

    # Attempt 2: ask macOS's built-in `sips` tool to convert the file to a plain JPEG,
    # then run that through the same normalization. Useful for formats Pillow rejects.
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
        # Both attempts failed, so the upload is not a usable image.
        # The API turns this ValueError into a clear message for the user.
        raise ValueError("This file is not an image the server can read") from exc
    finally:
        # The temporary sips output is only an intermediate file; always remove it.
        converted.unlink(missing_ok=True)
