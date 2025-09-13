from __future__ import annotations
import os
import struct
import zlib
from pathlib import Path
from typing import Any, Dict, List

from ..config import ASSETS_DIR
from .base import ImageProvider, ProviderResult


def _crc32(data: bytes) -> bytes:
    return struct.pack("!I", zlib.crc32(data) & 0xFFFFFFFF)


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    return struct.pack("!I", len(data)) + chunk_type + data + _crc32(chunk_type + data)


def _write_png_gray(path: Path, gray: List[List[int]]):
    height = len(gray)
    width = len(gray[0]) if height else 0
    # PNG header
    png = [b"\x89PNG\r\n\x1a\n"]
    # IHDR
    ihdr = struct.pack("!IIBBBBB", width, height, 8, 0, 0, 0, 0)  # 8-bit, grayscale
    png.append(_png_chunk(b"IHDR", ihdr))
    # IDAT (with per-scanline filter byte 0)
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw.extend(gray[y])
    compressed = zlib.compress(bytes(raw), level=9)
    png.append(_png_chunk(b"IDAT", compressed))
    # IEND
    png.append(_png_chunk(b"IEND", b""))
    path.write_bytes(b"".join(png))


def _gen_gray(width: int, height: int, seed: int) -> List[List[int]]:
    # Deterministic pattern: radial gradient + stripes seeded
    import math
    rnd = seed & 0xFFFF
    cx, cy = width / 2.0, height / 2.0
    arr: List[List[int]] = []
    for y in range(height):
        row: List[int] = []
        for x in range(width):
            dx, dy = x - cx, y - cy
            r = math.sqrt(dx*dx + dy*dy)
            base = 127 + 127 * math.cos((r / max(1.0, width/3.0)) + (rnd % 31) * 0.1)
            stripe = 50 * math.sin((x + 3 * y + (rnd % 13)) * 0.05)
            v = int(max(0, min(255, base + stripe)))
            row.append(v)
        arr.append(row)
    return arr


class NullProvider(ImageProvider):
    def generate(self, prompt_json: Dict[str, Any]) -> ProviderResult:
        seed = int(prompt_json.get("output", {}).get("seed", 0) or 0)
        width = min(1024, int(prompt_json.get("print_spec", {}).get("px_size", {}).get("width", 1024)))
        height = min(1024, int(prompt_json.get("print_spec", {}).get("px_size", {}).get("height", 1024)))
        gray = _gen_gray(width, height, seed)
        title = (prompt_json.get("design_title") or "design").replace(" ", "_")
        fname = f"{title}_{seed}.png"
        out_path = ASSETS_DIR / fname
        _write_png_gray(out_path, gray)
        return ProviderResult(file_path=str(out_path), width=width, height=height, image_gray=gray, response_payload={"provider": "null"})

