from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict

from ..config import PROMPTS_DIR


def save_prompt_json(prompt_json: Dict[str, Any], basename: str) -> Path:
    out = PROMPTS_DIR / f"{basename}.json"
    out.write_text(json.dumps(prompt_json, indent=2), encoding="utf-8")
    return out

