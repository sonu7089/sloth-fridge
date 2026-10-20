from __future__ import annotations

import io
import json
import re
from pathlib import Path

from PIL import Image, ImageOps

from . import config


class ImageError(RuntimeError):
    pass


def _prepare(image: Image.Image, max_edge: int, quality: int) -> bytes:
    image = ImageOps.exif_transpose(image)
    if image.mode not in ("RGB", "L") or image.mode == "L":
        image = image.convert("RGB")
    width, height = image.size
    longest = max(width, height)
    if longest > max_edge:
        scale = max_edge / float(longest)
        image = image.resize((max(1, int(width * scale)), max(1, int(height * scale))), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


def load_image_bytes(path: str | Path, max_edge: int | None = None, quality: int | None = None) -> bytes:
    path = Path(path)
    if not path.exists():
        raise ImageError(f"image not found: {path}")
    try:
        with Image.open(path) as image:
            return _prepare(
                image,
                max_edge or config.MAX_IMAGE_EDGE,
                quality or config.JPEG_QUALITY,
            )
    except ImageError:
        raise
    except Exception as exc:
        raise ImageError(f"could not read image {path}: {exc}") from exc


def image_to_base64(path: str | Path, max_edge: int | None = None, quality: int | None = None) -> str:
    import base64

    payload = load_image_bytes(path, max_edge, quality)
    return base64.b64encode(payload).decode("ascii")


def hash_bytes(payload: bytes) -> str:
    import hashlib

    return hashlib.sha256(payload).hexdigest()


def crop_views(payload: bytes, grid: int = 3, include_full: bool = True, overlap: float = 0.22) -> list[tuple[str, bytes]]:
    """Split an image into overlapping tiles so a weak vision model can see small objects."""
    with Image.open(io.BytesIO(payload)) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        width, height = image.size
        views: list[tuple[str, bytes]] = []
        if include_full:
            views.append(("full", payload))
        grid = max(1, grid)
        tile_width, tile_height = width // grid, height // grid
        pad_x, pad_y = int(tile_width * overlap), int(tile_height * overlap)
        for row in range(grid):
            for col in range(grid):
                left = max(0, col * tile_width - pad_x)
                top = max(0, row * tile_height - pad_y)
                right = min(width, (col + 1) * tile_width + pad_x)
                bottom = min(height, (row + 1) * tile_height + pad_y)
                if right - left < 32 or bottom - top < 32:
                    continue
                buffer = io.BytesIO()
                image.crop((left, top, right, bottom)).save(buffer, format="JPEG", quality=88, optimize=True)
                views.append((f"r{row}c{col}", buffer.getvalue()))
        return views


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> dict | list | None:
    if not text:
        return None
    candidate = text.strip()
    fenced = _FENCE.search(candidate)
    if fenced:
        candidate = fenced.group(1).strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    start = min([i for i in (candidate.find("{"), candidate.find("[")) if i != -1], default=-1)
    if start == -1:
        return None
    for end in range(len(candidate), start, -1):
        for closer in ("}", "]"):
            if candidate[end - 1 : end] != closer:
                continue
            try:
                return json.loads(candidate[start:end])
            except json.JSONDecodeError:
                continue
    repaired = re.sub(r",\s*([}\]])", r"\1", candidate[start:])
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        return None
