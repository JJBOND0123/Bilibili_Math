# Repository Guidelines

## Project layout
- `app.py`: Flask entry (routes, APIs, auth, dashboard/recommend endpoints).
- `models.py`: SQLAlchemy models.
- `config.py`: App / DB configuration (do not commit real credentials or cookies).
- `core/`: Core ML and data processing modules:
  - `topic_classifier.py`: Topic and difficulty classification (rule-based).
  - `quality_scorer.py`: Video quality scoring algorithm.
  - `recommend_engine.py`: Recommendation query engine (used by API layer).
  - `process_videos.py`: Batch enrichment script (writes to `video_enrichments` table).
- `spider/`: Bilibili data collection (writes into MySQL).
- `templates/`: Jinja2 templates.
- `static/`: Frontend assets (CSS/JS/images). User avatars live in `static/avatars/`.
- `docs/`: Documents, screenshots, DB migrations.

## Development Environment (Windows 11)
- **OS**: Windows 11
- **Python**: 3.10+ (recommend 3.12)
- **Editor**: VS Code with Python extension
- **File Encoding**: UTF-8 without BOM (all source files)

## Quick start (Windows)
- Create venv: `python -m venv .venv`
- Activate: `.\.venv\Scripts\activate`
- Install deps: `pip install -r requirements.txt`
- Run web: `flask --app app run --debug`

## Data / ML pipeline
- Fetch data: `python spider/bilibili_api.py`
- Enrich videos (topic/difficulty/quality_score/is_recommended): `python -m core.process_videos`
- Recommendation model (optional, StandardScaler + LogisticRegression): Train via external script
  - Output file: `recommend_model.joblib` (ignored by git)

## Coding conventions
- **File Encoding**: UTF-8 without BOM (mandatory for all `.py`, `.md`, `.html`, `.js`, `.css` files)
  - Use VS Code default settings (no BOM) or configure your editor accordingly
  - Verify with: Files should not start with UTF-8 BOM bytes (EF BB BF)
- **Python**: 4-space indent; `snake_case` for funcs/vars, `PascalCase` for classes
- **Code Style**: Keep functions small and avoid putting business logic into templates
- **Assets**: Avoid editing minified vendor assets unless necessary

## Security / local config
- Keep `config.py`'s `BILI_COOKIE` empty in committed code.
- Do not commit generated artifacts: `.venv/`, `__pycache__/`, logs, local screenshots, model dumps.

