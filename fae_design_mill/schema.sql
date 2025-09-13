PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS variable_list (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  description TEXT
);

CREATE TABLE IF NOT EXISTS variable_item (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  variable_list_id INTEGER NOT NULL,
  value TEXT NOT NULL,
  weight REAL NOT NULL DEFAULT 1.0,
  enabled INTEGER NOT NULL DEFAULT 1,
  cooldown_days INTEGER NOT NULL DEFAULT 0,
  tags TEXT,
  FOREIGN KEY(variable_list_id) REFERENCES variable_list(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_variable_item_list ON variable_item(variable_list_id);

CREATE TABLE IF NOT EXISTS variable_defaults (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  key_path TEXT NOT NULL UNIQUE,
  mode TEXT NOT NULL CHECK(mode IN ('LOCKED','WEIGHTED','RANDOM','SEQUENCE','LLM')),
  default_value TEXT,
  weight_profile_id INTEGER,
  sequence_pointer INTEGER DEFAULT 0,
  llm_template TEXT
);

CREATE TABLE IF NOT EXISTS weight_profile (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  description TEXT
);

CREATE TABLE IF NOT EXISTS weight_profile_item (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  weight_profile_id INTEGER NOT NULL,
  variable_list_id INTEGER NOT NULL,
  item_id INTEGER NOT NULL,
  weight REAL NOT NULL,
  FOREIGN KEY(weight_profile_id) REFERENCES weight_profile(id) ON DELETE CASCADE,
  FOREIGN KEY(variable_list_id) REFERENCES variable_list(id) ON DELETE CASCADE,
  FOREIGN KEY(item_id) REFERENCES variable_item(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS constraints (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  key TEXT NOT NULL UNIQUE,
  value TEXT
);

CREATE TABLE IF NOT EXISTS schema_preset (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  json_schema TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS generation_policy (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  min_days_between_similar_prompt INTEGER,
  min_novelty_score REAL,
  max_similarity_pct REAL,
  image_dupe_threshold INTEGER,
  prompt_dupe_threshold INTEGER,
  cooldown_multiplier REAL,
  topic_drift_rate REAL,
  provider TEXT,
  provider_params TEXT
);

CREATE TABLE IF NOT EXISTS design_run (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scheduled_for TEXT,
  status TEXT NOT NULL,
  reason TEXT,
  job_key TEXT UNIQUE,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_design_run_status ON design_run(status);

CREATE TABLE IF NOT EXISTS prompt_record (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  design_run_id INTEGER NOT NULL,
  json_payload TEXT NOT NULL,
  canonical_str TEXT NOT NULL,
  prompt_hash_simhash TEXT,
  prompt_hash_minhash TEXT,
  embedding BLOB,
  novelty_score REAL,
  staleness_score REAL,
  FOREIGN KEY(design_run_id) REFERENCES design_run(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS asset_record (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  design_run_id INTEGER NOT NULL,
  prompt_record_id INTEGER NOT NULL,
  provider TEXT NOT NULL,
  request_payload TEXT,
  response_payload TEXT,
  file_path TEXT,
  file_url TEXT,
  image_hash_phash TEXT,
  image_hash_dhash TEXT,
  width INTEGER,
  height INTEGER,
  dpi INTEGER,
  created_at TEXT NOT NULL,
  FOREIGN KEY(design_run_id) REFERENCES design_run(id) ON DELETE CASCADE,
  FOREIGN KEY(prompt_record_id) REFERENCES prompt_record(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_asset_hashes ON asset_record(image_hash_phash, image_hash_dhash);

CREATE TABLE IF NOT EXISTS cooldown_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  variable_item_id INTEGER NOT NULL,
  used_at TEXT NOT NULL,
  FOREIGN KEY(variable_item_id) REFERENCES variable_item(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS series_template (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  json_patch TEXT
);
