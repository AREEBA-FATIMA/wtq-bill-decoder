"""Image loading: fix EXIF orientation, normalise size, encode as PNG."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageOps

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def list_bills(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXTS)


def load_image_bytes(path: Path, max_side: int = 2000) -> bytes:
    """Return PNG bytes, auto-rotated and resized so the long side is <= max_side.

    Small images are upscaled to at least 1400 px on the long side so digits stay legible.
    """
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        long_side = max(img.size)
        target = min(max_side, max(long_side, 1400))
        if long_side != target:
            scale = target / long_side
            img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
