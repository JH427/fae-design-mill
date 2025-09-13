from __future__ import annotations
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .db import get_conn


def now_iso() -> str:
    return datetime.utcnow().isoformat()


def add_variable_list(name: str, description: str = "") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO variable_list(name, description) VALUES(?, ?)",
            (name, description),
        )
        if cur.lastrowid:
            conn.commit()
            return cur.lastrowid
        cur = conn.execute("SELECT id FROM variable_list WHERE name=?", (name,))
        return cur.fetchone()[0]


def add_variable_item(list_name: str, value: str, weight: float = 1.0, enabled: bool = True,
                      cooldown_days: int = 0, tags: Optional[List[str]] = None) -> int:
    lst_id = add_variable_list(list_name)
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO variable_item(variable_list_id, value, weight, enabled, cooldown_days, tags)
            VALUES(?,?,?,?,?,?)
            """,
            (lst_id, value, weight, 1 if enabled else 0, cooldown_days, json.dumps(tags or [])),
        )
        conn.commit()
        return cur.lastrowid


def ensure_variable_item(list_name: str, value: str, weight: float = 1.0, enabled: bool = True,
                          cooldown_days: int = 0, tags: Optional[List[str]] = None) -> bool:
    """Idempotently ensure a variable item exists; returns True if created."""
    lst_id = add_variable_list(list_name)
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT id FROM variable_item WHERE variable_list_id=? AND value=?",
            (lst_id, value),
        )
        if cur.fetchone():
            return False
        conn.execute(
            """
            INSERT INTO variable_item(variable_list_id, value, weight, enabled, cooldown_days, tags)
            VALUES(?,?,?,?,?,?)
            """,
            (lst_id, value, weight, 1 if enabled else 0, cooldown_days, json.dumps(tags or [])),
        )
        conn.commit()
        return True


def list_variable_lists() -> List[Dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT vl.id, vl.name, vl.description, COUNT(vi.id) AS item_count
            FROM variable_list vl
            LEFT JOIN variable_item vi ON vi.variable_list_id = vl.id
            GROUP BY vl.id, vl.name, vl.description
            ORDER BY vl.name
            """
        )
        return [dict(r) for r in cur.fetchall()]


def get_variable_list(name: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM variable_list WHERE name=?", (name,))
        row = cur.fetchone()
        return dict(row) if row else None


def list_variable_items(list_name: str) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT vi.* FROM variable_item vi
            JOIN variable_list vl ON vl.id = vi.variable_list_id
            WHERE vl.name = ?
            ORDER BY vi.id DESC
            """,
            (list_name,),
        )
        return [dict(r) for r in cur.fetchall()]


def scaffold_lists_for_defaults() -> int:
    """Ensure a variable_list exists for each key_path in variable_defaults."""
    count = 0
    dmap = get_defaults_map()
    for key_path in dmap.keys():
        # Create if missing
        existing = get_variable_list(key_path)
        if not existing:
            add_variable_list(key_path, description=f"Auto-created list for {key_path}")
            count += 1
    return count


def seed_comprehensive_variable_lists() -> int:
    """Seed reasonable options for most key paths so RANDOM works broadly."""
    created = 0
    # text.primary
    for v in [
        "FULLY AUTOMATED ENTERPRISES LLC",
        "FULLY AUTOMATED ENTERPRISES",
        "FAE", "FAE AUTOMATION", "FAE OPS",
    ]:
        if ensure_variable_item("text.primary", v, weight=1.0, cooldown_days=14):
            created += 1

    # text.layout
    for v in ["horizontal", "stacked", "badge", "circular"]:
        if ensure_variable_item("text.layout", v):
            created += 1

    # text.font_vibe
    for v in ["bold sans", "condensed", "mono", "rounded", "slab", "humanist"]:
        if ensure_variable_item("text.font_vibe", v):
            created += 1

    # text.text_treatment
    for v in ["solid", "outlined", "inline-shadow:none", "inline-shadow:soft", "etched", "inset", "stroke-only"]:
        if ensure_variable_item("text.text_treatment", v):
            created += 1

    # composition.framing
    for v in ["centered", "badge", "crest", "off-center"]:
        if ensure_variable_item("composition.framing", v):
            created += 1

    # composition.perspective
    for v in ["orthographic", "isometric", "oblique", "front"]:
        if ensure_variable_item("composition.perspective", v):
            created += 1

    # composition.balance
    for v in ["symmetrical", "asymmetrical", "radial", "triangular"]:
        if ensure_variable_item("composition.balance", v):
            created += 1

    # visual_style.detail_level
    for v in ["low", "medium", "medium-high", "high"]:
        if ensure_variable_item("visual_style.detail_level", v):
            created += 1

    # visual_style.shading
    for v in ["hatching/minimal", "none", "crosshatch", "dot-shade"]:
        if ensure_variable_item("visual_style.shading", v):
            created += 1

    # visual_style.texture
    for v in ["none", "paper", "grain", "halftone"]:
        if ensure_variable_item("visual_style.texture", v):
            created += 1

    # visual_style.finish
    for v in ["clean neon etching", "matte", "gloss", "metallic-outline"]:
        if ensure_variable_item("visual_style.finish", v):
            created += 1

    # background.type
    for v in ["transparent", "none", "solid"]:
        if ensure_variable_item("background.type", v):
            created += 1

    # background.drop_shadow
    for v in ["none", "soft", "hard"]:
        if ensure_variable_item("background.drop_shadow", v):
            created += 1

    # background.halo
    for v in ["none", "soft"]:
        if ensure_variable_item("background.halo", v):
            created += 1

    # background.background_elements
    for v in ["none", "grid", "guides", "circuit-traces"]:
        if ensure_variable_item("background.background_elements", v):
            created += 1

    # output.format
    for v in ["png", "webp"]:
        if ensure_variable_item("output.format", v):
            created += 1

    # output.transparent (bool as string)
    for v in ["true", "false"]:
        if ensure_variable_item("output.transparent", v):
            created += 1

    # constraints (bools as strings)
    for key in [
        "constraints.no_photographic_textures",
        "constraints.no_raster_noise",
        "constraints.no_background_box",
        "constraints.no_watermarks",
        "constraints.no_small_illegible_text",
    ]:
        for v in ["true", "false"]:
            if ensure_variable_item(key, v):
                created += 1

    # negative_prompt variations
    negs = [
        "no photo, no 3D render, no background, no gradients, no glow, no watermark, no mockup",
        "no photo realism, no raster textures, no background boxes, no glow, no watermarks",
        "avoid photographic textures, avoid 3D rendering, avoid background blocks, avoid glows",
    ]
    for v in negs:
        if ensure_variable_item("negative_prompt", v):
            created += 1

    # numeric-like options (stored as text; engine coerces types)
    for v in ["1", "2", "3", "4", "5"]:
        if ensure_variable_item("visual_style.line_weight_px", v):
            created += 1
    for v in ["4", "6", "8", "10"]:
        if ensure_variable_item("composition.padding_percent", v):
            created += 1
    for v in ["1", "2", "3"]:
        if ensure_variable_item("output.n_variations", v):
            created += 1
    for v in ["0.00", "0.01", "0.02", "0.04"]:
        if ensure_variable_item("color.gradient_map.clip_black", v):
            created += 1
    for v in ["0.00", "0.01", "0.02"]:
        if ensure_variable_item("color.gradient_map.clip_white", v):
            created += 1

    return created


def update_variable_item(item_id: int, **fields) -> None:
    if not fields:
        return
    cols = []
    params: List[Any] = []
    for k, v in fields.items():
        if k == "tags" and isinstance(v, list):
            v = json.dumps(v)
        if k == "enabled" and isinstance(v, bool):
            v = 1 if v else 0
        cols.append(f"{k} = ?")
        params.append(v)
    params.append(item_id)
    with get_conn() as conn:
        conn.execute(f"UPDATE variable_item SET {', '.join(cols)} WHERE id = ?", params)
        conn.commit()


def delete_variable_item(item_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM variable_item WHERE id = ?", (item_id,))
        conn.commit()


def set_default_mode(key_path: str, mode: str, default_value: Optional[Any] = None, weight_profile_id: Optional[int] = None, llm_template: Optional[str] = None):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO variable_defaults(key_path, mode, default_value, weight_profile_id, llm_template)
            VALUES(?,?,?,?,?)
            ON CONFLICT(key_path) DO UPDATE SET mode=excluded.mode, default_value=excluded.default_value, weight_profile_id=excluded.weight_profile_id, llm_template=excluded.llm_template
            """,
            (key_path, mode, json.dumps(default_value) if default_value is not None else None, weight_profile_id, llm_template),
        )
        conn.commit()


def get_defaults_map() -> Dict[str, Dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.execute("SELECT key_path, mode, default_value, weight_profile_id, sequence_pointer, llm_template FROM variable_defaults")
        out: Dict[str, Dict[str, Any]] = {}
        for r in cur.fetchall():
            out[r["key_path"]] = {
                "mode": r["mode"],
                "default_value": json.loads(r["default_value"]) if r["default_value"] else None,
                "weight_profile_id": r["weight_profile_id"],
                "sequence_pointer": r["sequence_pointer"],
                "llm_template": r["llm_template"],
            }
        return out


def get_policy() -> Dict[str, Any]:
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM generation_policy LIMIT 1")
        row = cur.fetchone()
        if not row:
            return {}
        return dict(row)


def _items_in_list(list_name: str) -> List[dict]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT vi.*, vl.name AS list_name FROM variable_item vi
            JOIN variable_list vl ON vl.id = vi.variable_list_id
            WHERE vl.name = ? AND vi.enabled = 1
            """,
            (list_name,),
        )
        return [dict(r) for r in cur.fetchall()]


def _is_in_cooldown(variable_item_id: int, cooldown_days: int, multiplier: float) -> bool:
    if cooldown_days <= 0:
        return False
    window_days = int(round(cooldown_days * multiplier))
    cutoff = datetime.utcnow() - timedelta(days=window_days)
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT COUNT(*) AS c FROM cooldown_log WHERE variable_item_id = ? AND used_at >= ?",
            (variable_item_id, cutoff.isoformat()),
        )
        return cur.fetchone()[0] > 0


def eligible_items(list_name: str, cooldown_multiplier: float = 1.0) -> List[dict]:
    items = _items_in_list(list_name)
    out: List[dict] = []
    for it in items:
        if not _is_in_cooldown(it["id"], int(it["cooldown_days"]), cooldown_multiplier):
            out.append(it)
    return out


def log_cooldown(item_ids: Sequence[int]):
    if not item_ids:
        return
    ts = now_iso()
    with get_conn() as conn:
        conn.executemany(
            "INSERT INTO cooldown_log(variable_item_id, used_at) VALUES(?, ?)",
            [(i, ts) for i in item_ids],
        )
        conn.commit()


def create_design_run(job_key: str, scheduled_for: Optional[str] = None) -> int:
    ts = now_iso()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO design_run(scheduled_for, status, reason, job_key, created_at, updated_at) VALUES(?, 'PENDING', '', ?, ?, ?)",
            (scheduled_for, job_key, ts, ts),
        )
        conn.commit()
        return cur.lastrowid


def update_design_run_status(run_id: int, status: str, reason: str = ""):
    with get_conn() as conn:
        conn.execute(
            "UPDATE design_run SET status=?, reason=?, updated_at=? WHERE id=?",
            (status, reason, now_iso(), run_id),
        )
        conn.commit()


def insert_prompt_record(run_id: int, json_payload: dict, canonical_str: str, simhash_hex: str, minhash_hex: str, novelty_score: float, staleness_score: float = 0.0) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO prompt_record(design_run_id, json_payload, canonical_str, prompt_hash_simhash, prompt_hash_minhash, novelty_score, staleness_score)
            VALUES(?,?,?,?,?,?,?)
            """,
            (run_id, json.dumps(json_payload, separators=(",", ":")), canonical_str, simhash_hex, minhash_hex, novelty_score, staleness_score),
        )
        conn.commit()
        return cur.lastrowid


def insert_asset_record(run_id: int, prompt_record_id: int, provider: str, request_payload: dict, response_payload: dict,
                        file_path: str, phash_hex: str, dhash_hex: str, width: int, height: int, dpi: int = 300) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO asset_record(design_run_id, prompt_record_id, provider, request_payload, response_payload, file_path, image_hash_phash, image_hash_dhash, width, height, dpi, created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                run_id,
                prompt_record_id,
                provider,
                json.dumps(request_payload, separators=(",", ":")) if request_payload else None,
                json.dumps(response_payload, separators=(",", ":")) if response_payload else None,
                file_path,
                phash_hex,
                dhash_hex,
                width,
                height,
                dpi,
                now_iso(),
            ),
        )
        conn.commit()
        return cur.lastrowid


def recent_prompt_hashes(limit: int = 100) -> List[Tuple[str, str]]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT prompt_hash_simhash, prompt_hash_minhash FROM prompt_record ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [(r[0] or "", r[1] or "") for r in cur.fetchall()]


def recent_asset_hashes(limit: int = 100) -> List[Tuple[str, str]]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT image_hash_phash, image_hash_dhash FROM asset_record ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [(r[0] or "", r[1] or "") for r in cur.fetchall()]


def seed_initial_data() -> int:
    # Seed lists and defaults based on the provided spec
    seeded = 0
    # Lists
    # text.secondary
    taglines = [
        "AI MONEY GANG", "Automate or Die", "Optimized Regards", "Cloud-Based Faith", "Glitch Angel Program",
        "Compliance Division", "Board of Infinite Optimization", "Unit 0042", "EmotionTech Dept.", "Office Drone Initiative",
        "Trust the Loop", "Systemic Elegance", "Algorithmic Rites", "Silent Operators", "Loop Priory",
        "Zero-Touch Commerce", "Hands-Off Hustle", "Autonomy Engine", "Ghost Shift", "Night Audit Crew",
        "Beta Mode Forever", "Capital Alchemy", "Infinite Throughput", "Latency Church", "Machine Novitiate", "Process Sorcery"
    ]
    for s in taglines:
        add_variable_item("text.secondary", s, weight=1.0, cooldown_days=14)
        seeded += 1

    # subject
    subjects = [
        "executive android in suit", "floating blueprint cube", "barcode crown sigil", "microchip rosette", "paperclip halo",
        "ethernet vines crest", "neon audit stamp", "orbital compliance seal", "up-and-right ribbon chart",
        "monk with circuit prayer beads", "mecha falcon emblem", "skeleton key glyph", "hex portal with rulers",
        "infrared ring array", "vector lotus PCB", "server monolith totem", "wireframe gauntlet handshake",
        "laser-cut workflow knot", "AI heraldic shield"
    ]
    for s in subjects:
        add_variable_item("subject", s, weight=1.0, cooldown_days=30)
        seeded += 1

    # icons_symbols
    icons = [
        "circuit glyphs", "subtle panel lines", "arrow ribbon up-right", "microchip rosette", "barcode crown",
        "QR sigil", "ethernet vines", "compliance seal", "loading spinner badge", "keyhole eyes"
    ]
    for s in icons:
        add_variable_item("icons_symbols", s, weight=1.0, cooldown_days=12)
        seeded += 1

    # genre_tags clusters as items under visual_style.genre_tags
    clusters = [
        ["logo-mark","engraved-line","sci-fi-monk"],
        ["wireframe","blueprint-overlay","retro-futurism"],
        ["digital-surrealism","minimalist-monogram","techno-gothic"],
    ]
    for cl in clusters:
        add_variable_item("visual_style.genre_tags", json.dumps(cl), weight=1.0, cooldown_days=8)
        seeded += 1

    # composition.style
    for s in ["vector", "line-art", "blueprint-overlay", "wireframe", "engraved-line"]:
        add_variable_item("composition.style", s, weight=1.0, cooldown_days=7)
        seeded += 1

    # gradient_map.scheme
    for s in ["Inferno", "Viridis", "Plasma", "Magma", "Turbo"]:
        add_variable_item("color.gradient_map.scheme", s, weight=1.0, cooldown_days=10)
        seeded += 1

    # Defaults / modes
    set_default_mode("text.primary", "LOCKED", "FULLY AUTOMATED ENTERPRISES LLC")
    set_default_mode("text.secondary", "WEIGHTED")
    set_default_mode("text.layout", "LOCKED", "horizontal | stacked")
    set_default_mode("text.font_vibe", "LOCKED", ["bold sans", "condensed"])
    set_default_mode("text.text_treatment", "LOCKED", ["solid", "outlined", "inline-shadow:none"])

    set_default_mode("subject", "WEIGHTED")

    set_default_mode("composition.style", "RANDOM")
    set_default_mode("composition.framing", "LOCKED", "centered")
    set_default_mode("composition.perspective", "LOCKED", "orthographic")
    set_default_mode("composition.balance", "LOCKED", "symmetrical")
    set_default_mode("composition.padding_percent", "LOCKED", 6)

    set_default_mode("visual_style.genre_tags", "WEIGHTED")
    set_default_mode("visual_style.line_weight_px", "LOCKED", 3)
    set_default_mode("visual_style.detail_level", "LOCKED", "medium-high")
    set_default_mode("visual_style.shading", "LOCKED", "hatching/minimal")
    set_default_mode("visual_style.texture", "LOCKED", "none")
    set_default_mode("visual_style.finish", "LOCKED", "clean neon etching")

    set_default_mode("color.allow_gradients", "LOCKED", True)
    set_default_mode("color.gradient_map.scheme", "RANDOM")
    set_default_mode("color.gradient_map.apply_to", "LOCKED", ["strokes"])
    set_default_mode("color.gradient_map.reverse", "LOCKED", False)
    set_default_mode("color.gradient_map.clip_black", "LOCKED", 0.02)
    set_default_mode("color.gradient_map.clip_white", "LOCKED", 0.00)

    set_default_mode("icons_symbols", "RANDOM")

    set_default_mode("background.type", "LOCKED", "transparent")
    set_default_mode("background.drop_shadow", "LOCKED", "none")
    set_default_mode("background.halo", "LOCKED", "none")
    set_default_mode("background.background_elements", "LOCKED", "none")

    set_default_mode("print_spec.px_size.width", "LOCKED", 5400)
    set_default_mode("print_spec.px_size.height", "LOCKED", 4500)
    set_default_mode("print_spec.dpi_target", "LOCKED", 300)
    set_default_mode("print_spec.safe_margin_px", "LOCKED", 150)
    set_default_mode("print_spec.stroke_outline_px", "LOCKED", 10)
    set_default_mode("print_spec.use_white_keyline_for_stickers", "LOCKED", False)

    set_default_mode("output.format", "LOCKED", "png")
    set_default_mode("output.transparent", "LOCKED", True)
    set_default_mode("output.n_variations", "LOCKED", 1)
    set_default_mode("output.seed", "LOCKED", 427)

    set_default_mode("references.style_refs", "LOCKED", [])
    set_default_mode("references.logo_ref", "LOCKED", "")
    set_default_mode("references.color_ref", "LOCKED", [])

    set_default_mode("constraints.no_photographic_textures", "LOCKED", True)
    set_default_mode("constraints.no_raster_noise", "LOCKED", True)
    set_default_mode("constraints.no_background_box", "LOCKED", True)
    set_default_mode("constraints.no_watermarks", "LOCKED", True)
    set_default_mode("constraints.no_small_illegible_text", "LOCKED", True)

    set_default_mode("negative_prompt", "LOCKED", "no photo, no 3D render, no background, no rectangle or box framing, no gradients, no glow, no watermark, no mockup")

    return seeded
