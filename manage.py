#!/usr/bin/env python
import argparse
import sys
from pathlib import Path

from fae_design_mill import config
from fae_design_mill.db import init_db
from fae_design_mill.repositories import seed_initial_data
from fae_design_mill.scheduler import run_once, run_scheduler


def serve(host: str, port: int):
    try:
        from fae_design_mill.app import create_app
        app = create_app()
    except Exception as e:
        print("Flask server not available or failed to initialize:", e)
        print("Install dependencies: pip install -r requirements.txt")
        sys.exit(1)
    app.run(host=host, port=port, debug=True)


def main():
    parser = argparse.ArgumentParser(prog="fae-design-mill")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db", help="Create SQLite schema and folders")
    sub.add_parser("seed", help="Seed initial variable lists and policy")
    sub.add_parser("seed-all-lists", help="Seed comprehensive options for most variables")
    sub.add_parser("scaffold-lists", help="Ensure a variable_list exists for each key path in defaults")
    sub.add_parser("run-once", help="Run a single generation now")
    sub.add_parser("run-scheduler", help="Run the daily scheduler in foreground")

    pserve = sub.add_parser("serve", help="Start Flask API/UI")
    pserve.add_argument("--host", default="127.0.0.1")
    pserve.add_argument("--port", default=5000, type=int)

    args = parser.parse_args()

    # Ensure data dirs
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    config.PROMPTS_DIR.mkdir(parents=True, exist_ok=True)

    if args.cmd == "init-db":
        init_db()
        print(f"DB initialized at {config.DB_PATH}")
    elif args.cmd == "seed":
        init_db()
        count = seed_initial_data()
        print(f"Seeded {count} items (lists + defaults + policy)")
    elif args.cmd == "scaffold-lists":
        init_db()
        from fae_design_mill.repositories import scaffold_lists_for_defaults
        n = scaffold_lists_for_defaults()
        print(f"Ensured lists for {n} key paths")
    elif args.cmd == "run-once":
        init_db()
        result = run_once()
        print("Run result:", result)
    elif args.cmd == "run-scheduler":
        init_db()
        run_scheduler()
    elif args.cmd == "serve":
        init_db()
        serve(args.host, args.port)
    elif args.cmd == "seed-all-lists":
        init_db()
        from fae_design_mill.repositories import seed_comprehensive_variable_lists, scaffold_lists_for_defaults
        scaffold_lists_for_defaults()
        n = seed_comprehensive_variable_lists()
        print(f"Seeded {n} options across variables")


if __name__ == "__main__":
    main()
