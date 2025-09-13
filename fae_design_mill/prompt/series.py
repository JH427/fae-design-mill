from __future__ import annotations
from typing import Any, Dict, List


def apply_json_patch(doc: Dict[str, Any], patch_ops: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Minimal RFC6902 subset: op in {add, replace, remove}; path as /a/b/c; no array indices
    def get_parent_and_key(d: Dict[str, Any], path: str):
        parts = [p for p in path.split('/') if p]
        cur = d
        for p in parts[:-1]:
            if p not in cur or not isinstance(cur[p], dict):
                cur[p] = {}
            cur = cur[p]
        return cur, parts[-1] if parts else ""

    for op in patch_ops or []:
        typ = op.get("op")
        path = op.get("path", "/")
        if typ in ("add", "replace"):
            parent, key = get_parent_and_key(doc, path)
            parent[key] = op.get("value")
        elif typ == "remove":
            parent, key = get_parent_and_key(doc, path)
            parent.pop(key, None)
    return doc

