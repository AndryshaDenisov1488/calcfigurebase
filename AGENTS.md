# Purpose
Flask service for importing, storing, and analyzing ISUCalcFS competition data.

# Architecture
- Entry: `app.py`; routes: `routes/`; services: `services/`; parsers: `parsers/`.
- UI: `templates/`, `static/`; tests: `tests/`; migrations: `migrations/`; operations: `scripts/`.

# Commands
- Install: `python -m pip install -r requirements.txt`
- Dev: `python app.py`
- Test: `python -m pytest`
- Lint/typecheck/build: `unknown`

# Conventions
- Start with targeted search; do not open neighboring projects without a proven contract.
- Import changes require a narrow parser test using anonymized input.
- Do not commit `instance/`, uploads, databases, personal source files, logs, or backups.

# Integration
- `figurebase.ru` is a separate neighboring product, not part of this Git repository.
- No cross-project dependency is assumed without contract evidence.

# Verification
Run targeted parser/service tests, then `python -m pytest` when proportionate. Check template and static behavior together for UI changes.

# Deploy
After verifier PASS and automatic push, deploy runtime changes automatically via `README.md`/`scripts/` for `calc.figurebase.ru`, then check `calc-figurebase` and the smoke scenario. Skip when the user opts out; backup and recovery are mandatory before migration.
