from __future__ import annotations
from typing import Any, Dict
from .schema import ordered_dump


def canonical_dump(obj: Dict[str, Any]) -> str:
    # For MVP, canonical == sorted-keys compact JSON
    return ordered_dump(obj)


def canonical_similarity_dump(obj: Dict[str, Any]) -> str:
    """Dump only creative fields for similarity hashing to avoid static noise.

    Focus on fields that materially change design content; drop print_spec,
    references, most constraints/background boilerplate so SimHash/MinHash
    are sensitive to creative variation.
    """
    slim: Dict[str, Any] = {}
    slim["design_title"] = obj.get("design_title")
    t = obj.get("text", {}) or {}
    slim["text"] = {
        "primary": t.get("primary"),
        "secondary": t.get("secondary"),
        "layout": t.get("layout"),
        "font_vibe": t.get("font_vibe"),
        "text_treatment": t.get("text_treatment"),
    }
    slim["subject"] = obj.get("subject")
    comp = obj.get("composition", {}) or {}
    slim["composition"] = {
        "style": comp.get("style"),
        "framing": comp.get("framing"),
        "perspective": comp.get("perspective"),
        "balance": comp.get("balance"),
    }
    vs = obj.get("visual_style", {}) or {}
    slim["visual_style"] = {
        "genre_tags": vs.get("genre_tags"),
        "shading": vs.get("shading"),
        "finish": vs.get("finish"),
    }
    color = obj.get("color", {}) or {}
    gm = (color.get("gradient_map") or {})
    slim["color"] = {
        "allow_gradients": color.get("allow_gradients"),
        "gradient_map": {"scheme": gm.get("scheme"), "apply_to": gm.get("apply_to"), "reverse": gm.get("reverse")},
    }
    slim["icons_symbols"] = obj.get("icons_symbols")
    slim["negative_prompt"] = obj.get("negative_prompt")
    return ordered_dump(slim)
