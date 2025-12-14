# Repository Guidelines

## Project Structure & Module Organization
- `app.py`: Flask entrypoint (routes, APIs, auth, recommendations).
- `models.py`: SQLAlchemy models and DB access.
- `config.py`: Flask/MySQL configuration (edit locally).
- `spider/`: Bilibili crawler (`spider/bilibili_api.py`) that fetches and writes video rows to MySQL.
- `templates/`: Jinja2 templates for server-rendered pages.
- `static/`: Frontend assets (CSS/JS/images); user avatars are stored in `static/avatars/`.
- `docs/`: screenshots and project documentation.
- `train_model.py`: trains/exports `subject_classifier.pkl` (optional).
- `force_fix.py`: re-downloads vendored ECharts/WordCloud JS into `static/js/` (network).

## Build, Test, and Development Commands
- Create and activate a venv (Windows): `python -m venv .venv` then `.\.venv\Scripts\activate`
- Install dependencies: `pip install -r requirements.txt`
- Run the web app: `flask --app app run --debug` (requires a reachable MySQL configured in `config.py`)
- Crawl/import data: `python spider/bilibili_api.py`
- Train the text classifier (optional): `python train_model.py`
- Refresh offline JS assets (optional): `python force_fix.py`

## Coding Style & Naming Conventions
- Python: 4-space indentation, PEP 8 naming (`snake_case` functions/vars, `PascalCase` classes), keep files UTF-8.
- Prefer small, focused functions; avoid pushing business logic into templates.
- Frontend: keep JS/CSS under `static/`; avoid editing minified vendor files unless necessary.

## Testing Guidelines
- `pytest` is included, but there is no dedicated `tests/` directory yet.
- New tests: `tests/test_*.py` with clear, deterministic unit tests (text parsing, metrics, crawler helpers).
- Run tests: `pytest`

## Commit & Pull Request Guidelines
- Commit messages commonly use Conventional Commits-style prefixes: `feat:`, `fix:`, `ui:`, `docs:`, `chore:`.
- Keep summaries short and imperative; Chinese or English is fine, but be consistent within a PR.
- PRs should include: problem statement, approach, how to run/verify, screenshots for UI changes (update `docs/screenshots/` when relevant), and any DB/schema notes.

## Security & Local Configuration
- Do not commit real credentials, Bilibili cookies, or session tokens; treat `config.py` and `spider/bilibili_api.py` as local-only configuration.
- Avoid committing generated artifacts (`__pycache__/`, `.venv/`, uploaded `static/avatars/`, large binaries) unless the change explicitly requires it.