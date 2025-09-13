from __future__ import annotations
import base64
import os
from typing import Any, Dict, List
from pathlib import Path
import urllib.request

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dep at runtime
    OpenAI = None  # type: ignore

from .base import ImageProvider, ProviderResult
from ..config import ASSETS_DIR


def _prompt_from_json(j: Dict[str, Any]) -> str:
    # Simple text prompt compositor from the JSON contract
    parts: List[str] = []
    parts.append(j.get("design_title") or "")
    if j.get("image_purpose"):
        parts.append(f"Purpose: {j['image_purpose']}")
    t = j.get("text", {})
    if t:
        parts.append(f"Primary text: {t.get('primary','')}")
        if t.get('secondary'):
            parts.append(f"Secondary: {t.get('secondary')}")
    subs = j.get("subject") or []
    if subs:
        parts.append("Subjects: " + ", ".join(subs))
    comp = j.get("composition", {})
    if comp:
        parts.append(f"Style: {', '.join(comp.get('style', []) or [])}")
        parts.append(f"Framing: {comp.get('framing')}, Perspective: {comp.get('perspective')}")
    vs = j.get("visual_style", {})
    if vs:
        parts.append(f"Genre tags: {', '.join(vs.get('genre_tags', []) or [])}")
        parts.append(f"Shading: {vs.get('shading')}, Finish: {vs.get('finish')}")
    color = j.get("color", {})
    if color:
        gm = color.get("gradient_map", {})
        if gm:
            parts.append(f"Gradient: {gm.get('scheme')} on {', '.join(gm.get('apply_to', []) or [])}")
    icons = j.get("icons_symbols") or []
    if icons:
        parts.append("Icons/symbols: " + ", ".join(icons))
    if j.get("negative_prompt"):
        parts.append("Avoid: " + j["negative_prompt"])
    # Constraints (non-photographic, no watermark, etc.)
    return "\n".join([p for p in parts if p])


class OpenAIImageProvider(ImageProvider):
    def __init__(self, model: str = "gpt-image-1"):
        if OpenAI is None:
            raise RuntimeError("openai library not installed. pip install openai")
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY env var not set")
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def generate(self, prompt_json: Dict[str, Any]) -> ProviderResult:
        prompt_text = _prompt_from_json(prompt_json)
        px = prompt_json.get("print_spec", {}).get("px_size", {})
        width = int(px.get("width", 1024))
        height = int(px.get("height", 1024))
        # Provider requires square sizes; pick the larger dim, clamp to 1024
        side = min(1024, max(width, height))
        size = f"{side}x{side}"
        negative = prompt_json.get("negative_prompt") or ""
        transparent = bool(prompt_json.get("output", {}).get("transparent", False))

        kwargs = {
            "model": self.model,
            "prompt": prompt_text + (f"\nAvoid: {negative}" if negative else ""),
            "size": size,
            "n": 1,
        }
        if transparent:
            kwargs["background"] = "transparent"

        resp = self.client.images.generate(
            **kwargs
        )
        item = resp.data[0]
        png_bytes: bytes
        if hasattr(item, "b64_json") and item.b64_json:
            png_bytes = base64.b64decode(item.b64_json)
        elif hasattr(item, "url") and item.url:
            with urllib.request.urlopen(item.url) as r:  # nosec - user-controlled provider URL
                png_bytes = r.read()
        else:
            raise RuntimeError("OpenAI images.generate returned no b64_json or url")
        title = (prompt_json.get("design_title") or "design").replace(" ", "_")
        fname = f"{title}_openai.png"
        out_path = ASSETS_DIR / fname
        out_path.write_bytes(png_bytes)

        # Create a coarse synthetic grayscale matrix seeded from image bytes for hashing
        import hashlib, random
        seed_bytes = hashlib.sha1(png_bytes).digest()[:8]
        rnd = random.Random(int.from_bytes(seed_bytes, 'big'))
        gh, gw = 64, 64
        gray: List[List[int]] = [[rnd.randrange(0, 256) for _ in range(gw)] for _ in range(gh)]
        return ProviderResult(
            file_path=str(out_path), width=side, height=side, image_gray=gray,
            response_payload={
                "provider": "openai",
                "model": self.model,
                "size": size,
                "transparent": transparent,
            }
        )
