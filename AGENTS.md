# Repository Guidelines

## Project Structure & Module Organization
`app/` contains backend code. `app/main.py` is the FastAPI entrypoint, `app/api/` defines routes and schemas, `app/agent/` holds orchestration logic, `app/tool/` contains rendering and image-QA tools, and `app/util/` provides shared helpers (renderer/uploader).  
`tests/` contains pytest-based checks (currently `tests/test_service.py`).  
`frontend/` contains the static web UI and Nginx config used by Docker Compose.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate`: create and activate local env.
- `pip install -r requirements.txt`: install backend dependencies.
- `playwright install chromium`: install browser runtime required by renderer.
- `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`: run API locally.
- `docker compose up -d --build`: start backend + frontend in containers.
- `pytest tests/test_service.py -v`: run service tests.

## Coding Style & Naming Conventions
Use Python style consistent with existing code:
- 4-space indentation, UTF-8, and clear module/class/function docstrings.
- `snake_case` for modules/functions/variables, `PascalCase` for classes.
- Keep API contracts in `app/api/schemas.py`; avoid duplicating request/response models elsewhere.
- Prefer explicit logging (`logging.getLogger(__name__)`) over `print`.

## Testing Guidelines
Use `pytest` and name files/functions as `test_*.py` and `test_*`.  
Prefer small, deterministic tests for new logic (mock remote LLM/VL calls where possible).  
`tests/test_service.py` is an end-to-end smoke test and depends on configured `.env` plus reachable model endpoints.

## Commit & Pull Request Guidelines
Follow the repository’s Conventional Commit pattern seen in history, e.g. `feat: ...`, `fix: ...`.  
Keep commits focused and atomic.  
PRs should include:
- what changed and why,
- config/env var impacts,
- test evidence (commands run),
- screenshots or sample API responses when behavior/UI output changes.

## Security & Configuration Tips
Copy `.env.example` to `.env` and keep secrets local only. Never commit API keys or internal host credentials.  
When changing ports or exposure, preserve the localhost binding pattern in `docker-compose.yml` unless broader exposure is explicitly required.
