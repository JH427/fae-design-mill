from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ProviderResult:
    file_path: str
    width: int
    height: int
    image_gray: List[List[int]]  # grayscale matrix for hashing
    response_payload: Optional[Dict[str, Any]] = None


class ImageProvider:
    def generate(self, prompt_json: Dict[str, Any]) -> ProviderResult:  # pragma: no cover - interface
        raise NotImplementedError

