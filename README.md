FAE Design Mill

Daily, de-duplicated merch prompt + image generator with a DB–driven variables system, novelty safeguards, and a minimal Flask UI. Built to run hands‑off (scheduler), stay fresh (cooldowns, mutation, drift), and plug into different image providers.

Why it exists
- Generate one or more design prompts per day, forever, without getting stale.
- Avoid duplicates at the prompt level (SimHash/MinHash) and image level (pHash/dHash).
- Drive creativity from curated lists in SQLite, with LOCKED/WEIGHTED/RANDOM/SEQUENCE/LLM modes per key.
- Admin from a simple UI: variables editor, policy controls, run dashboard, and DB admin.

Highlights
- Prompt engine with per-key modes, cooldowns, and mutation operators
- SimHash + MinHash on a “creative subset” of the JSON for robust prompt de‑dupe
- Perceptual dHash/pHash image de‑dupe with retry/mutate workflow
- Variables UI with Quick Add (paste multi-line / comma / JSON array), list CRUD
- Providers: synthetic local generator (no deps) and OpenAI Images adapter
- Scheduler + CLI for daily hands-off operation
- Everything persisted in SQLite; assets and prompts saved to disk

Screens
- Dashboard: run cards with live status and image thumbnails
- Variables: per-key modes, provider selection, generator policy, quick list adds
- DB Admin: browse/edit tables, run SQL (read-only by default), backup/vacuum

Quick start
1) Python env and deps
   - python -m venv .venv
   - .venv/Scripts/Activate.ps1    # Windows PowerShell
   - pip install -r requirements.txt
2) Configure environment (optional)
   - Copy `.env.example` → `.env`
   - Set `FAE_PROVIDER=null` (local) or `openai` + `OPENAI_API_KEY`
3) Initialize DB and seed
   - python manage.py init-db
   - python manage.py seed              # brand lists (subjects, icons, etc.)
   - python manage.py scaffold-lists    # create lists for all keys
   - python manage.py seed-all-lists    # seed sensible options for most keys
4) Generate once (prompt + PNG under data/)
   - python manage.py run-once
5) Run the UI (optional)
   - python manage.py serve --host 0.0.0.0 --port 8000
   - Open http://localhost:8000
6) Scheduler (optional)
   - python manage.py run-scheduler

CLI commands
- init-db: create tables
- seed: seed brand lists and defaults
- scaffold-lists: ensure a list exists for every key path
- seed-all-lists: seed general options across variables
- run-once: single generation
- run-scheduler: daily scheduler loop
- serve: start Flask API/UI

Configuration (.env)
- FAE_PROVIDER: `null` | `openai` (default `null`)
- OPENAI_API_KEY: required for `openai`
- FAE_LLM_MODEL: model for LLM field generation (default `gpt-4o-mini`)
- FAE_SCHEDULE_HOUR: hour of day (0–23) for the daily job (default 9)

Providers
- null (local): writes deterministic grayscale PNGs; honors `output.seed` and size caps; no network
- openai: uses gpt-image‑1, square sizes (≤1024), optional transparent background; no seed support

Prompt engine (how values are chosen)
- Modes per key path: LOCKED, WEIGHTED, RANDOM, SEQUENCE, LLM
- Lists: each key can have a `variable_list` of options with weight, enabled, cooldown_days, tags
- Type‑aware coercion for numeric/bool keys selected from lists
- Multi‑picks for list‑valued keys (e.g., subject×3, icons×2, style×2)
- Fallback: if a list is empty due to cooldowns, re-sample ignoring cooldowns to stay valid
- Mutation: rotates/redraws high‑impact fields to escape similarity (subject, icons, style, genre tags, gradient scheme, tagline)

Novelty & de‑duplication
- Hashing scope: SimHash/MinHash run on a “creative subset” of the JSON, not boilerplate
- Prompt gate: reject only when both SimHash (≤ threshold) and MinHash Jaccard (≥ threshold) indicate a dupe; thresholds are configurable in the UI
- Image gate: pHash Hamming distance ≤ threshold ⇒ mutate & retry

UI routes
- /            Dashboard with thumbnails and live progress
- /variables   Key modes, provider & policy controls, variable lists (with Quick Add)
- /admin/db    DB admin (browse, edit, SQL, backup, vacuum)
- /assets/*    Serves generated images

API (selected)
- POST /api/run                # body: {force_new?, random_seed?}
- POST /api/preview            # returns prospective prompt + hashes
- GET  /api/runs               # recent runs + file_url
- GET/POST /api/variables      # list/create variable lists
- GET/POST /api/variables/<list>
- POST /api/variables/<list>/<id>
- GET/POST /api/defaults       # per-key mode/default/LLM template
- POST /api/policy             # update thresholds/provider

Data model (SQLite)
- variable_list / variable_item: per‑key option lists with weight, enabled, cooldown, tags
- variable_defaults: per‑key mode (LOCKED/WEIGHTED/RANDOM/SEQUENCE/LLM), default, sequence pointer, LLM template
- generation_policy: thresholds (dupe, novelty), cooldown multiplier, topic drift, provider
- design_run / prompt_record / asset_record: run lifecycle, canonical JSON, hashes, file paths
- cooldown_log: enforces time‑based reuse limits

Project layout
- manage.py                      CLI entry points
- fae_design_mill/
  - app.py, api/routes.py        Flask app + routes
  - db.py, schema.sql            SQLite + DDL
  - repositories.py              DB helpers, seeding, scaffolding
  - scheduler.py                 Orchestration + daily scheduler
  - prompt/                      Engine, hashing, canonicalization, rules
  - providers/                   Provider interface + adapters (null, openai)
  - ui/templates/                Jinja2 templates (Dashboard, Variables, DB admin)
  - storage/files.py             Prompt JSON persistence

Storage
- data/fae.db           SQLite database
- data/assets/          Generated PNGs (unique filenames per run)
- data/prompts/         Saved prompt JSONs

Troubleshooting
- “Missing or invalid subject” on preview: seed lists (`seed`, `scaffold-lists`, `seed-all-lists`) and/or use Quick Add on `/variables`.
- Frequent SKIPPED due to similarity: raise “Prompt dupe threshold” to 8–16 on `/variables` → Generator Controls; ensure subject/icons/style lists are well‑populated; use “New Prompt” to force mutation and roll a new seed.
- OpenAI errors: remove unsupported params (already done), ensure API key, stay within size/model constraints.

Roadmap
- Weight profiles per key
- Embedding‑based novelty score
- Variation batches per run and gallery view
- Lightbox and image metadata sidecar
