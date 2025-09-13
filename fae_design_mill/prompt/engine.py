from __future__ import annotations
import json
import random
from typing import Any, Dict, List, Tuple

from ..repositories import (
    get_defaults_map,
    eligible_items,
    log_cooldown,
    get_policy,
    recent_prompt_hashes,
)
from .schema import default_frame, validate_prompt
from .canonical import canonical_dump, canonical_similarity_dump
from .hashers import simhash64, minhash_hex
from .rules import apply_mutual_exclusions
from ..llm import generate_value_for_key


def _resolve_value(mode: str, key_path: str, defaults_map: Dict[str, Dict[str, Any]], policy: Dict[str, Any]) -> Tuple[Any, List[int]]:
    # Returns value, used_item_ids
    used_ids: List[int] = []
    dm = defaults_map.get(key_path, {})
    cooldown_multiplier = float(policy.get("cooldown_multiplier", 1.0))
    if mode == "LOCKED":
        return dm.get("default_value"), used_ids
    elif mode == "LLM":
        # Use LLM to synthesize a value; if unavailable, fall back to RANDOM/LOCKED
        value = generate_value_for_key(key_path, {}, dm.get("llm_template"))
        if value is not None:
            return value, used_ids
        # Fallback path: try RANDOM
        mode = "RANDOM"
    elif mode == "RANDOM":
        items = eligible_items(key_path, cooldown_multiplier)
        if not items:
            # Fallback: ignore cooldown if list exists but all are cooling down
            items = eligible_items(key_path, 0.0)
        if not items:
            return dm.get("default_value"), used_ids
        choice = random.choices(items, weights=[max(0.0001, i["weight"]) for i in items], k=1)[0]
        used_ids.append(choice["id"])
        # list-valued fields
        if key_path in _list_multi_keys():
            k = _list_multi_keys()[key_path]
            vals = [_coerce_value(key_path, choice["value"])]
            pool = [i for i in items if i["id"] != choice["id"]]
            if pool and k > 1:
                extra = random.sample(pool, min(len(pool), k-1))
                vals.extend([_coerce_value(key_path, e["value"]) for e in extra])
                used_ids.extend([e["id"] for e in extra])
            return vals, used_ids
        return _coerce_value(key_path, choice["value"]), used_ids
    elif mode == "WEIGHTED":
        items = eligible_items(key_path, cooldown_multiplier)
        if not items:
            items = eligible_items(key_path, 0.0)
        if not items:
            return dm.get("default_value"), used_ids
        choice = random.choices(items, weights=[max(0.0001, i["weight"]) for i in items], k=1)[0]
        used_ids.append(choice["id"])
        # Special case: visual_style.genre_tags list is stored as JSON array strings in DB
        if key_path == "visual_style.genre_tags":
            try:
                return json.loads(choice["value"]), used_ids
            except Exception:
                return [choice["value"]], used_ids
        if key_path in _list_multi_keys():
            k = _list_multi_keys()[key_path]
            pool = [i for i in items if i["id"] != choice["id"]]
            vals = [_coerce_value(key_path, choice["value"])]
            if pool:
                extra = random.sample(pool, min(len(pool), k-1))
                vals.extend([_coerce_value(key_path, e["value"]) for e in extra])
                used_ids.extend([e["id"] for e in extra])
            return vals, used_ids
        return _coerce_value(key_path, choice["value"]), used_ids
    elif mode == "SEQUENCE":
        items = eligible_items(key_path, cooldown_multiplier)
        if not items:
            items = eligible_items(key_path, 0.0)
        if not items:
            return dm.get("default_value"), used_ids
        items_sorted = sorted(items, key=lambda x: x["id"])  # stable order
        idx = int(dm.get("sequence_pointer") or 0)
        choice = items_sorted[idx % len(items_sorted)]
        used_ids.append(choice["id"])
        return choice["value"], used_ids
    else:
        return dm.get("default_value"), used_ids


def build_prompt(design_title: str = "") -> Tuple[Dict[str, Any], Dict[str, str], List[int]]:
    defaults_map = get_defaults_map()
    policy = get_policy()
    obj = default_frame()
    if not design_title:
        # derive title from text.secondary + first subject (if any)
        design_title = "FAE Design"
    obj["design_title"] = design_title

    key_paths = list(defaults_map.keys())
    used_items: List[int] = []
    for kp, conf in defaults_map.items():
        val, used = _resolve_value(conf["mode"], kp, defaults_map, policy)
        used_items.extend(used)
        # Set value into nested obj by kp path
        _set_by_path(obj, kp, val)

    # Apply mutual exclusions and finish shaping
    apply_mutual_exclusions(obj)

    # Validation
    errs = validate_prompt(obj)
    if errs:
        raise ValueError("Prompt validation failed: " + "; ".join(errs))

    # Canonical + hashes (use slim canonical for similarity)
    canon_full = canonical_dump(obj)
    canon_sim = canonical_similarity_dump(obj)
    hashes = {
        "simhash": simhash64(canon_sim),
        "minhash": minhash_hex(canon_sim),
    }

    return obj, hashes, used_items


def novelty_check(hashes: Dict[str, str], policy: Dict[str, Any]) -> Tuple[bool, str]:
    sim_thresh = int(policy.get("prompt_dupe_threshold", 3))
    max_jaccard = float(policy.get("max_similarity_pct", 0.92))
    # Use both SimHash and MinHash (Jaccard) checks
    recent = recent_prompt_hashes(200)
    from .hashers import hamming_distance_hex, minhash_similarity_hex
    for simhash_hex, minhash_prev in recent:
        if not simhash_hex:
            continue
        dist = hamming_distance_hex(hashes["simhash"], simhash_hex)
        sim_close = dist <= sim_thresh
        jac_close = False
        jac = None
        if minhash_prev:
            jac = minhash_similarity_hex(hashes["minhash"], minhash_prev)
            jac_close = jac >= max_jaccard
        # Be lenient: only reject when both metrics deem it too similar.
        if sim_close and (jac_close or jac is None):
            # If we don't have minhash_prev (legacy records), use simhash alone
            return False, f"SimHash distance {dist} <= {sim_thresh}"
        if jac_close and sim_close:
            return False, f"MinHash similarity {jac:.2f} >= {max_jaccard:.2f} and SimHash {dist} <= {sim_thresh}"
    return True, "ok"


def mutate_prompt(obj: Dict[str, Any]) -> Dict[str, Any]:
    """Mutate prompt to increase novelty.

    Strategy: rotate existing lists if present; otherwise redraw from DB
    ignoring cooldowns for high-impact fields.
    """
    # Rotate existing values
    for key in ("subject", "icons_symbols"):
        vals = obj.get(key, [])
        if isinstance(vals, list) and vals:
            obj[key] = vals[1:] + vals[:1]
    # Redraw a few fields ignoring cooldowns
    def redraw_list(key_path: str, k: int = 1):
        items = eligible_items(key_path, cooldown_multiplier=0.0)
        if not items:
            return None
        pick = random.sample(items, min(len(items), k))
        vals = [ _coerce_value(key_path, p["value"]) for p in pick ]
        return vals if k > 1 else vals[0]

    # Try redraws
    new_subj = redraw_list("subject", 3)
    if new_subj:
        obj["subject"] = new_subj
    new_icons = redraw_list("icons_symbols", 2)
    if new_icons:
        obj["icons_symbols"] = new_icons
    new_style = redraw_list("composition.style", 2)
    if new_style:
        obj.setdefault("composition", {})["style"] = new_style
    # genre_tags stored as JSON arrays in DB; redraw one cluster
    items = eligible_items("visual_style.genre_tags", cooldown_multiplier=0.0)
    if items:
        import json as _json
        choice = random.choice(items)
        try:
            obj.setdefault("visual_style", {})["genre_tags"] = _json.loads(choice["value"])  # type: ignore
        except Exception:
            obj.setdefault("visual_style", {})["genre_tags"] = [choice["value"]]
    scheme = redraw_list("color.gradient_map.scheme", 1)
    if scheme:
        obj.setdefault("color", {}).setdefault("gradient_map", {})["scheme"] = scheme
    sec = redraw_list("text.secondary", 1)
    if sec:
        obj.setdefault("text", {})["secondary"] = sec
    return obj


def _set_by_path(obj: Dict[str, Any], key_path: str, value: Any) -> None:
    parts = key_path.split('.')
    cur = obj
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


def _list_multi_keys() -> Dict[str, int]:
    return {
        "subject": 3,
        "icons_symbols": 2,
        "composition.style": 2,
        "text.font_vibe": 2,
        "text.text_treatment": 3,
    }


_INT_KEYS = {
    "composition.padding_percent",
    "visual_style.line_weight_px",
    "print_spec.px_size.width",
    "print_spec.px_size.height",
    "print_spec.dpi_target",
    "print_spec.safe_margin_px",
    "print_spec.stroke_outline_px",
    "output.n_variations",
    "output.seed",
}

_FLOAT_KEYS = {
    "color.gradient_map.clip_black",
    "color.gradient_map.clip_white",
}

_BOOL_KEYS = {
    "color.allow_gradients",
    "color.gradient_map.reverse",
    "output.transparent",
    "print_spec.use_white_keyline_for_stickers",
    "constraints.no_photographic_textures",
    "constraints.no_raster_noise",
    "constraints.no_background_box",
    "constraints.no_watermarks",
    "constraints.no_small_illegible_text",
}


def _coerce_value(key_path: str, v: Any) -> Any:
    # Coerce from stored TEXT to target type when needed
    if key_path in _INT_KEYS:
        try:
            return int(v)
        except Exception:
            return v
    if key_path in _FLOAT_KEYS:
        try:
            return float(v)
        except Exception:
            return v
    if key_path in _BOOL_KEYS:
        if isinstance(v, bool):
            return v
        s = str(v).strip().lower()
        if s in ("true", "1", "yes", "y"): return True
        if s in ("false", "0", "no", "n"): return False
        return v
    return v
