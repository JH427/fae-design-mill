import sqlite3
from contextlib import contextmanager
from pathlib import Path
from .config import DB_PATH, ROOT_DIR


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_conn():
    conn = _connect()
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    schema_path = Path(__file__).with_name("schema.sql")
    sql = schema_path.read_text(encoding="utf-8")
    with get_conn() as conn:
        conn.executescript(sql)
        # Migrations: ensure variable_defaults has llm_template and allows LLM
        try:
            cur = conn.execute("PRAGMA table_info(variable_defaults)")
            cols = [r[1] for r in cur.fetchall()]
            needs_llm_template = "llm_template" not in cols
            # Check mode constraint by reading sqlite_master
            cur = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='variable_defaults'")
            ddl = (cur.fetchone() or ("",))[0] or ""
            allows_llm = "'LLM'" in ddl
            if needs_llm_template or not allows_llm:
                # Rebuild table to add llm_template and allow LLM in CHECK
                conn.execute("ALTER TABLE variable_defaults RENAME TO variable_defaults_old")
                conn.executescript(
                    """
                    CREATE TABLE variable_defaults (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      key_path TEXT NOT NULL UNIQUE,
                      mode TEXT NOT NULL CHECK(mode IN ('LOCKED','WEIGHTED','RANDOM','SEQUENCE','LLM')),
                      default_value TEXT,
                      weight_profile_id INTEGER,
                      sequence_pointer INTEGER DEFAULT 0,
                      llm_template TEXT
                    );
                    INSERT INTO variable_defaults(id, key_path, mode, default_value, weight_profile_id, sequence_pointer)
                    SELECT id, key_path, mode, default_value, weight_profile_id, sequence_pointer FROM variable_defaults_old;
                    DROP TABLE variable_defaults_old;
                    """
                )
        except Exception:
            pass

        # Migrations: add provider columns if missing
        try:
            cur = conn.execute("PRAGMA table_info(generation_policy)")
            cols = [r[1] for r in cur.fetchall()]
            if "provider" not in cols:
                conn.execute("ALTER TABLE generation_policy ADD COLUMN provider TEXT")
            if "provider_params" not in cols:
                conn.execute("ALTER TABLE generation_policy ADD COLUMN provider_params TEXT")
        except Exception:
            pass
        # Ensure a policy row exists
        cur = conn.execute("SELECT COUNT(*) AS c FROM generation_policy")
        if cur.fetchone()[0] == 0:
            from .config import POLICY_DEFAULTS, DEFAULT_PROVIDER
            conn.execute(
                """
                INSERT INTO generation_policy (
                    min_days_between_similar_prompt,
                    min_novelty_score,
                    max_similarity_pct,
                    image_dupe_threshold,
                    prompt_dupe_threshold,
                    cooldown_multiplier,
                    topic_drift_rate,
                    provider,
                    provider_params
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    POLICY_DEFAULTS["min_days_between_similar_prompt"],
                    POLICY_DEFAULTS["min_novelty_score"],
                    POLICY_DEFAULTS["max_similarity_pct"],
                    POLICY_DEFAULTS["image_dupe_threshold"],
                    POLICY_DEFAULTS["prompt_dupe_threshold"],
                    POLICY_DEFAULTS["cooldown_multiplier"],
                    POLICY_DEFAULTS["topic_drift_rate"],
                    DEFAULT_PROVIDER,
                    None,
                ),
            )
            conn.commit()
