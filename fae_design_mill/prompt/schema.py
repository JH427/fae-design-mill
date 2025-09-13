from __future__ import annotations
import json
from collections import OrderedDict
from typing import Any, Dict, List


def default_frame() -> Dict[str, Any]:
    # Minimal default frame, filled by engine using DB defaults per key_path
    return OrderedDict(
        {
            "design_title": "",
            "image_purpose": "merch: t-shirt | hoodie | sticker | mug",
            "text": OrderedDict(
                {
                    "primary": "",
                    "secondary": "",
                    "layout": "horizontal | stacked",
                    "font_vibe": [],
                    "text_treatment": [],
                }
            ),
            "subject": [],
            "composition": OrderedDict(
                {
                    "style": [],
                    "framing": "centered",
                    "perspective": "orthographic",
                    "balance": "symmetrical",
                    "padding_percent": 6,
                }
            ),
            "visual_style": OrderedDict(
                {
                    "genre_tags": [],
                    "line_weight_px": 3,
                    "detail_level": "medium-high",
                    "shading": "hatching/minimal",
                    "texture": "none",
                    "finish": "clean neon etching",
                }
            ),
            "color": OrderedDict(
                {
                    "allow_gradients": True,
                    "gradient_map": OrderedDict(
                        {
                            "scheme": "Inferno",
                            "apply_to": ["strokes"],
                            "reverse": False,
                            "clip_black": 0.02,
                            "clip_white": 0.00,
                        }
                    ),
                }
            ),
            "icons_symbols": [],
            "background": OrderedDict(
                {
                    "type": "transparent",
                    "drop_shadow": "none",
                    "halo": "none",
                    "background_elements": "none",
                }
            ),
            "print_spec": OrderedDict(
                {
                    "px_size": OrderedDict({"width": 5400, "height": 4500}),
                    "dpi_target": 300,
                    "safe_margin_px": 150,
                    "stroke_outline_px": 10,
                    "use_white_keyline_for_stickers": False,
                }
            ),
            "output": OrderedDict(
                {
                    "format": "png",
                    "transparent": True,
                    "n_variations": 1,
                    "seed": 427,
                }
            ),
            "references": OrderedDict(
                {"style_refs": [], "logo_ref": "", "color_ref": []}
            ),
            "constraints": OrderedDict(
                {
                    "no_photographic_textures": True,
                    "no_raster_noise": True,
                    "no_background_box": True,
                    "no_watermarks": True,
                    "no_small_illegible_text": True,
                }
            ),
            "negative_prompt": "",
        }
    )


def validate_prompt(obj: Dict[str, Any]) -> List[str]:
    # Lightweight validation tailored to the schema shared
    errs: List[str] = []

    def req(d: Dict[str, Any], key: str, typ):
        if key not in d or not isinstance(d[key], typ):
            errs.append(f"Missing or invalid {key}")

    req(obj, "design_title", str)
    req(obj, "image_purpose", str)
    req(obj, "text", dict)
    req(obj, "subject", list)
    req(obj, "composition", dict)
    req(obj, "visual_style", dict)
    req(obj, "color", dict)
    req(obj, "icons_symbols", list)
    req(obj, "background", dict)
    req(obj, "print_spec", dict)
    req(obj, "output", dict)
    req(obj, "references", dict)
    req(obj, "constraints", dict)
    req(obj, "negative_prompt", str)

    # Spot checks
    if "px_size" in obj.get("print_spec", {}):
        px = obj["print_spec"]["px_size"]
        if not isinstance(px, dict) or not isinstance(px.get("width"), int) or not isinstance(px.get("height"), int):
            errs.append("print_spec.px_size must have int width/height")
    if obj.get("output", {}).get("format") not in ("png", "webp"):
        errs.append("output.format must be 'png' or 'webp'")
    return errs


def ordered_dump(obj: Dict[str, Any]) -> str:
    # Deterministic compact JSON dump with sorted keys
    return json.dumps(obj, separators=(",", ":"), sort_keys=True)

