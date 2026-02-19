# Lumi Draw

[中文文档](README_CN.md)

LLM-powered agentic image generation service. Accepts natural-language descriptions and autonomously produces images via **HTML Native** rendering, with built-in VL (Vision-Language) model quality assurance.

## Architecture

```
User Request
     │
     ▼
┌─────────────────┐
│   FastAPI API    │  POST /api/v1/generate
└────────┬────────┘
         │
         ▼
┌──────────────────────────────────┐
│   LangGraph Agent                │
│                                  │
│   Tools:                         │
│   ├── generate_html_image        │
│   └── check_image_quality (VL)   │
│                                  │
│   Middleware:                     │
│   ├── PatchToolCalls             │
│   ├── ContextEditing             │
│   ├── Summarization              │
│   └── ModelFallback              │
└──────────────────────────────────┘
         │
         ▼
┌──────────────┐     ┌──────────────┐
│  Playwright  │────▶│   Uploader   │
│  (Chromium)  │     │ Local / SFTP │
└──────────────┘     └──────────────┘
```

## Project Structure

```
lumi-draw/
├── .env.example          # Environment variable template
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── README.md             # English docs (this file)
├── README_CN.md          # Chinese docs
├── app/
│   ├── main.py           # FastAPI entry point
│   ├── config.py         # Centralized settings (env vars)
│   ├── api/
│   │   ├── routes.py     # API endpoints
│   │   └── schemas.py    # Request / response models
│   ├── agent/
│   │   ├── service.py    # ImageGenAgenticService
│   │   └── prompt.py     # Agent system prompt
│   ├── model/
│   │   └── llm_config.py # LLM configuration
│   ├── tool/
│   │   │   ├── html_render.py
│   │   └── image_qa.py   # VL quality check
│   └── util/
│       ├── renderer.py   # Playwright rendering engine
│       └── uploader.py   # Image upload (local / SFTP)
└── tests/
    └── test_service.py
```

## Quick Start

### 1. Clone & Configure

```bash
git clone https://github.com/Finn7X/lumi-draw.git
cd lumi-draw
cp .env.example .env
# Edit .env with your actual values
```

### 2. Run with Docker (Recommended)

```bash
docker compose up -d --build
```

The service will be available at `http://localhost:8000`.

### 3. Run Locally

```bash
python -m venv .venv
source .venv/bin/activate   # Linux / macOS
# .venv\Scripts\activate    # Windows

pip install -r requirements.txt
playwright install chromium

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Reference

### Health Check

```http
GET /api/v1/health
```

```json
{ "status": "ok", "service": "lumi-draw" }
```

### Generate Image

```http
POST /api/v1/generate
Content-Type: application/json

{
  "query": "Draw a user login flowchart",
  "user_id": "optional-user-id"
}
```

```json
{
  "status": "success",
  "result": "Image generated:\n![image](http://...xxx.png)",
  "error": null
}
```

### Interactive Docs

| UI | URL |
|----|-----|
| Swagger | `http://localhost:8000/docs` |
| ReDoc | `http://localhost:8000/redoc` |

## Configuration

All settings are managed via environment variables (see [`.env.example`](.env.example)):

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_PORT` | Listen port | `8000` |
| `LOG_LEVEL` | Logging level | `info` |
| `LLM_PRIMARY_*` | Primary LLM settings | minimax-m21 |
| `LLM_PRIMARY_THINKING_ENABLED` | Kimi K2.5 thinking mode switch | `true` |
| `LLM_FALLBACK_*` | Fallback LLM settings | kimi-k2 |
| `VL_MODEL_URL` | VL quality-check model endpoint | — |
| `LANGFUSE_*` | Langfuse observability | — |
| `IMAGE_*` | Image upload target | — |
| `RENDER_OUTPUT_DIR` | Temp directory for rendered PNGs | `/tmp/image_gen` |

## License

MIT
