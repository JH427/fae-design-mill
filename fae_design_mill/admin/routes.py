from __future__ import annotations
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from typing import List, Dict, Any
import os
import shutil
from ..db import get_conn
from ..config import DB_PATH, DATA_DIR


admin_bp = Blueprint("admin", __name__)


def list_tables() -> List[str]:
    with get_conn() as conn:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        return [r[0] for r in cur.fetchall()]


def table_info(name: str) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.execute(f"PRAGMA table_info({name})")
        cols = []
        for r in cur.fetchall():
            cols.append({
                "cid": r[0],
                "name": r[1],
                "type": r[2],
                "notnull": r[3],
                "dflt_value": r[4],
                "pk": r[5],
            })
        return cols


def primary_key(name: str) -> str | None:
    cols = table_info(name)
    for c in cols:
        if c["pk"]:
            return c["name"]
    # Fall back to 'id'
    for c in cols:
        if c["name"].lower() == "id":
            return c["name"]
    return None


@admin_bp.route("/db")
def db_home():
    rows = []
    with get_conn() as conn:
        for t in list_tables():
            cnt = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            rows.append({"table": t, "count": cnt})
    return render_template("db_admin.html", tables=rows, db_path=str(DB_PATH))


@admin_bp.route("/db/download")
def db_download():
    return send_file(DB_PATH, as_attachment=True, download_name=os.path.basename(DB_PATH))


@admin_bp.route("/db/backup", methods=["POST"])
def db_backup():
    backups = DATA_DIR / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = backups / f"fae_{ts}.db"
    shutil.copy2(DB_PATH, out)
    return redirect(url_for("admin.db_home"))


@admin_bp.route("/db/vacuum", methods=["POST"])
def db_vacuum():
    with get_conn() as conn:
        conn.execute("VACUUM")
    return redirect(url_for("admin.db_home"))


@admin_bp.route("/db/table/<name>")
def db_table(name: str):
    cols = table_info(name)
    pk = primary_key(name)
    page = max(1, int(request.args.get("page", 1)))
    limit = min(200, int(request.args.get("limit", 50)))
    offset = (page - 1) * limit
    with get_conn() as conn:
        cur = conn.execute(f"SELECT * FROM {name} ORDER BY {pk or cols[0]['name']} DESC LIMIT ? OFFSET ?", (limit, offset))
        rows = [dict(r) for r in cur.fetchall()]
        total = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
    return render_template("db_table.html", table=name, cols=cols, rows=rows, pk=pk, page=page, limit=limit, total=total)


@admin_bp.route("/db/table/<name>/delete/<pk_value>", methods=["POST"])
def db_delete(name: str, pk_value: str):
    pk = primary_key(name)
    if not pk:
        return "No primary key; delete not allowed", 400
    with get_conn() as conn:
        conn.execute(f"DELETE FROM {name} WHERE {pk} = ?", (pk_value,))
        conn.commit()
    return redirect(url_for("admin.db_table", name=name))


@admin_bp.route("/db/table/<name>/edit/<pk_value>", methods=["GET", "POST"])
def db_edit(name: str, pk_value: str):
    pk = primary_key(name)
    if not pk:
        return "No primary key; edit not allowed", 400
    cols = table_info(name)
    with get_conn() as conn:
        if request.method == "POST":
            data = request.form.to_dict()
            # Build UPDATE, exclude pk from update set
            sets = []
            params: list[Any] = []
            for c in cols:
                col = c["name"]
                if col == pk:
                    continue
                if col in data:
                    sets.append(f"{col} = ?")
                    params.append(data[col])
            params.append(pk_value)
            if sets:
                conn.execute(f"UPDATE {name} SET {', '.join(sets)} WHERE {pk} = ?", params)
                conn.commit()
            return redirect(url_for("admin.db_table", name=name))
        row = conn.execute(f"SELECT * FROM {name} WHERE {pk} = ?", (pk_value,)).fetchone()
        if not row:
            return "Row not found", 404
        rowd = dict(row)
    return render_template("db_edit.html", table=name, pk=pk, pk_value=pk_value, cols=cols, row=rowd)


@admin_bp.route("/db/sql", methods=["GET", "POST"])
def db_sql():
    result = None
    error = None
    sql_text = ""
    allow_write = False
    if request.method == "POST":
        sql_text = request.form.get("sql", "").strip()
        allow_write = request.form.get("allow_write") == "on"
        try:
            with get_conn() as conn:
                if not allow_write:
                    # Simple safety: only allow SELECT/PRAGMA/EXPLAIN/WITH
                    for stmt in [s.strip() for s in sql_text.split(';') if s.strip()]:
                        up = stmt.upper()
                        if not (up.startswith("SELECT") or up.startswith("PRAGMA") or up.startswith("EXPLAIN") or up.startswith("WITH")):
                            raise ValueError("Only read-only statements allowed without write permission")
                cur = conn.execute(sql_text)
                # Try fetching rows if any
                try:
                    rows = cur.fetchall()
                    cols = [d[0] for d in cur.description] if cur.description else []
                    result = {"cols": cols, "rows": [list(r) for r in rows]}
                except Exception:
                    result = {"ok": True}
        except Exception as e:
            error = str(e)
    return render_template("db_sql.html", result=result, error=error, sql_text=sql_text, allow_write=allow_write)

