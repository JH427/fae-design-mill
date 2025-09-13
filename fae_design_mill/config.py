from pathlib import Path
import os

# Load .env if present
try:
    from dotenv import load_dotenv
except Exception:  # optional dep
    load_dotenv = None  # type: ignore

# Project root (folder containing this package)
ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
ASSETS_DIR = DATA_DIR / "assets"
PROMPTS_DIR = DATA_DIR / "prompts"
DB_PATH = DATA_DIR / "fae.db"

# Load .env from project root early
if load_dotenv:
    env_path = ROOT_DIR / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)

# Scheduling defaults
DEFAULT_SCHEDULE_HOUR = int(os.getenv("FAE_SCHEDULE_HOUR", "9"))  # 09:00 local

# Provider selection (can extend to use env)
DEFAULT_PROVIDER = os.getenv("FAE_PROVIDER", "null")

# Generation policy defaults (if DB empty)
POLICY_DEFAULTS = {
    "min_days_between_similar_prompt": 7,
    "min_novelty_score": 0.55,
    "max_similarity_pct": 0.92,
    "image_dupe_threshold": 5,
    "prompt_dupe_threshold": 3,
    "cooldown_multiplier": 1.0,
    "topic_drift_rate": 0.2,
}
