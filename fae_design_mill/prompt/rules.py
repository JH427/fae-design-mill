from __future__ import annotations
from typing import Dict, Any


def apply_mutual_exclusions(obj: Dict[str, Any]) -> None:
    # Example: if style includes 'vector', keep shading minimal
    styles = set(obj.get("composition", {}).get("style", []) or [])
    if "vector" in styles:
        obj.setdefault("visual_style", {}).setdefault("shading", "hatching/minimal")
    # Example: forbid gradients if negative_prompt says no gradients
    neg = obj.get("negative_prompt", "")
    if "no gradients" in neg:
        obj.setdefault("color", {}).setdefault("allow_gradients", False)

