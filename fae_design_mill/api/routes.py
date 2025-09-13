from __future__ import annotations
from flask import Blueprint, jsonify, request
import os

from ..scheduler import run_once
from ..prompt.engine import build_prompt
from ..repositories import (
    get_defaults_map,
    set_default_mode,
    get_policy,
    list_variable_lists,
    list_variable_items,
    add_variable_item,
    delete_variable_item,
    update_variable_item,
    add_variable_list,
    scaffold_lists_for_defaults,
    seed_comprehensive_variable_lists,
)
from ..db import get_conn


api_bp = Blueprint("api", __name__)


@api_bp.route("/preview", methods=["POST"])
def preview():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "FAE Preview")
    prompt, hashes, _ = build_prompt(design_title=title)
    return jsonify({"prompt": prompt, "hashes": hashes})


@api_bp.route("/run", methods=["POST"])
def run_now():
    data = request.get_json(silent=True) or {}
    force_new = bool(data.get("force_new", False))
    random_seed = bool(data.get("random_seed", False))
    res = run_once(force_new=force_new, random_seed=random_seed)
    return jsonify(res)

@api_bp.route("/runs", methods=["GET"])
def list_runs():
    # minimal: last 20 assets
    from ..db import get_conn
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT dr.id as run_id, dr.status, pr.id as prompt_id, ar.id as asset_id, ar.file_path, ar.created_at
            FROM design_run dr
            LEFT JOIN prompt_record pr ON pr.design_run_id = dr.id
            LEFT JOIN asset_record ar ON ar.design_run_id = dr.id
            ORDER BY dr.id DESC LIMIT 20
            """
        )
        rows = []
        for r in cur.fetchall():
            d = dict(r)
            fp = d.get("file_path") or ""
            if fp:
                d["file_url"] = f"/assets/{os.path.basename(fp)}"
            rows.append(d)
    return jsonify({"items": rows})


@api_bp.route("/defaults", methods=["GET","POST"])
def defaults():
    if request.method == "GET":
        return jsonify({"defaults": get_defaults_map()})
    data = request.get_json(silent=True) or {}
    key_path = data.get("key_path")
    mode = data.get("mode")
    default_value = data.get("default_value")
    llm_template = data.get("llm_template")
    if not key_path or not mode:
        return jsonify({"error": "key_path and mode required"}), 400
    set_default_mode(key_path, mode, default_value, None, llm_template)
    return jsonify({"ok": True})

@api_bp.route("/policy", methods=["POST"])  # update selected generator policy fields
def set_policy():
    data = request.get_json(silent=True) or {}
    provider = data.get("provider")
    fields = {}
    # Whitelist editable fields
    for key in [
        "min_days_between_similar_prompt",
        "min_novelty_score",
        "max_similarity_pct",
        "image_dupe_threshold",
        "prompt_dupe_threshold",
        "cooldown_multiplier",
        "topic_drift_rate",
    ]:
        if key in data and data[key] is not None:
            fields[key] = data[key]
    with get_conn() as conn:
        sets = []
        params = []
        if provider:
            sets.append("provider = ?")
            params.append(provider.lower())
        for k, v in fields.items():
            sets.append(f"{k} = ?")
            params.append(v)
        if sets:
            conn.execute(f"UPDATE generation_policy SET {', '.join(sets)} WHERE id=(SELECT id FROM generation_policy LIMIT 1)", params)
            conn.commit()
    return jsonify({"ok": True, "policy": get_policy()})


# Variable lists & items
@api_bp.route("/variables", methods=["GET", "POST"])
def variables_root():
    if request.method == "GET":
        return jsonify({"lists": list_variable_lists()})
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    description = data.get("description", "")
    if not name:
        return jsonify({"error": "name required"}), 400
    add_variable_list(name, description)
    return jsonify({"ok": True})


@api_bp.route("/variables/ensure", methods=["POST"])
def variables_ensure_lists():
    data = request.get_json(silent=True) or {}
    key_path = data.get("key_path")
    created = 0
    if key_path:
        if not get_variable_list(key_path):
            add_variable_list(key_path, description=f"List for {key_path}")
            created = 1
        return jsonify({"ok": True, "created": created})
    # If no key specified, scaffold all
    n = scaffold_lists_for_defaults()
    return jsonify({"ok": True, "created": n})


@api_bp.route("/variables/seed-defaults", methods=["POST"])
def variables_seed_defaults():
    # Seeds a broad set of default options for many keys
    n = seed_comprehensive_variable_lists()
    return jsonify({"ok": True, "seeded": n})


@api_bp.route("/variables/<list_name>", methods=["GET", "POST"])
def variables_list_items(list_name: str):
    if request.method == "GET":
        return jsonify({"items": list_variable_items(list_name)})
    data = request.get_json(silent=True) or {}
    values = data.get("values")
    weight = float(data.get("weight", 1.0))
    cooldown_days = int(data.get("cooldown_days", 0))
    enabled = bool(data.get("enabled", True))
    tags = data.get("tags") or []
    if isinstance(values, list):
        ids = []
        for v in values:
            ids.append(add_variable_item(list_name, str(v), weight, enabled, cooldown_days, tags))
        return jsonify({"ok": True, "created": ids})
    elif isinstance(values, str):
        iid = add_variable_item(list_name, values, weight, enabled, cooldown_days, tags)
        return jsonify({"ok": True, "created": [iid]})
    else:
        return jsonify({"error": "values must be string or list of strings"}), 400


@api_bp.route("/variables/<list_name>/<int:item_id>", methods=["POST"])
def variables_item_update(list_name: str, item_id: int):
    data = request.get_json(silent=True) or {}
    action = data.get("action")
    if action == "delete":
        delete_variable_item(item_id)
        return jsonify({"ok": True})
    fields = {}
    for k in ("value", "weight", "cooldown_days", "enabled", "tags"):
        if k in data:
            fields[k] = data[k]
    update_variable_item(item_id, **fields)
    return jsonify({"ok": True})
