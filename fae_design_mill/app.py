from __future__ import annotations
from flask import Flask, render_template, send_from_directory
from pathlib import Path
import json
from .db import get_conn
from .db import init_db
from .api.routes import api_bp
from .admin.routes import admin_bp
from .config import ASSETS_DIR


def create_app() -> Flask:
    template_dir = Path(__file__).with_name("ui") / "templates"
    app = Flask(__name__, template_folder=str(template_dir))
    init_db()
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/variables")
    def variables():
        with get_conn() as conn:
            cur = conn.execute("SELECT * FROM variable_defaults ORDER BY key_path")
            rows = []
            for r in cur.fetchall():
                dv = r["default_value"]
                try:
                    dv_str = json.dumps(json.loads(dv)) if dv else ""
                except Exception:
                    dv_str = dv or ""
                rows.append({
                    "key_path": r["key_path"],
                    "mode": r["mode"],
                    "default_value_str": dv_str,
                    "llm_template": r["llm_template"],
                })
            pol = conn.execute("SELECT provider FROM generation_policy LIMIT 1").fetchone()
            provider = pol["provider"] if pol else None
            # Fetch existing list names
            cur2 = conn.execute("SELECT name FROM variable_list")
            list_names = set([r["name"] for r in cur2.fetchall()])
        return render_template("variables.html", rows=rows, provider=provider, list_names=list_names)

    @app.route("/variables/list/<name>")
    def variable_items_page(name: str):
        # Server renders items; edits are done via API from client JS
        with get_conn() as conn:
            # Fetch list id and items
            vlist = conn.execute("SELECT * FROM variable_list WHERE name=?", (name,)).fetchone()
            items = []
            if vlist:
                cur = conn.execute(
                    "SELECT * FROM variable_item WHERE variable_list_id = ? ORDER BY id DESC",
                    (vlist["id"],),
                )
                items = [dict(r) for r in cur.fetchall()]
        return render_template("variable_items.html", list_name=name, items=items)

    @app.route("/health")
    def health():
        return {"ok": True}

    @app.route("/assets/<path:filename>")
    def assets(filename: str):
        # Serve generated images from assets directory
        return send_from_directory(str(ASSETS_DIR), filename, as_attachment=False)

    return app
