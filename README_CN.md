# Lumi Draw

[English](README.md)

基于 LLM 的 Agentic 图片生成服务。接收自然语言描述，通过 **HTML Native** 方式渲染图片，内置 VL（视觉语言）模型质量检查。

## 架构

```
用户请求
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
│   工具:                           │
│   ├── generate_html_image        │
│   └── check_image_quality (VL)   │
│                                  │
│   中间件:                         │
│   ├── PatchToolCalls             │
│   ├── ContextEditing             │
│   ├── Summarization              │
│   └── ModelFallback              │
└──────────────────────────────────┘
         │
         ▼
┌──────────────┐     ┌──────────────┐
│  Playwright  │────▶│   上传器      │
│  (Chromium)  │     │ 本地 / SFTP  │
└──────────────┘     └──────────────┘
```

## 项目结构

```
lumi-draw/
├── .env.example          # 环境变量模板
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── README.md             # 英文文档
├── README_CN.md          # 中文文档（本文件）
├── app/
│   ├── main.py           # FastAPI 入口
│   ├── config.py         # 统一配置管理（读取环境变量）
│   ├── api/
│   │   ├── routes.py     # API 路由
│   │   └── schemas.py    # 请求 / 响应模型
│   ├── agent/
│   │   ├── service.py    # ImageGenAgenticService 核心服务
│   │   └── prompt.py     # Agent 系统提示词
│   ├── model/
│   │   └── llm_config.py # LLM 模型配置
│   ├── tool/
│   │   ├── html_render.py      # HTML 渲染工具
│   │   └── image_qa.py        # VL 质量检查工具
│   └── util/
│       ├── renderer.py   # Playwright 渲染引擎
│       └── uploader.py   # 图片上传（本地 / SFTP）
└── tests/
    └── test_service.py
```

## 快速开始

### 1. 克隆 & 配置

```bash
git clone https://github.com/Finn7X/lumi-draw.git
cd lumi-draw
cp .env.example .env
# 编辑 .env 填入实际配置值
```

### 2. Docker 部署（推荐）

```bash
docker compose up -d --build
```

服务启动后访问 `http://localhost:8000`。

### 3. 本地运行

```bash
python -m venv .venv
source .venv/bin/activate   # Linux / macOS
# .venv\Scripts\activate    # Windows

pip install -r requirements.txt
playwright install chromium

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API 接口

### 健康检查

```http
GET /api/v1/health
```

```json
{ "status": "ok", "service": "lumi-draw" }
```

### 生成图片

```http
POST /api/v1/generate
Content-Type: application/json

{
  "query": "画一个用户登录流程图",
  "user_id": "可选的用户ID"
}
```

```json
{
  "status": "success",
  "result": "已为您生成图片：\n用户登录流程图\n![图片](http://...xxx.png)",
  "error": null
}
```

### 交互式文档

| 文档 | 地址 |
|------|------|
| Swagger UI | `http://localhost:8000/docs` |
| ReDoc | `http://localhost:8000/redoc` |

## 配置说明

所有配置通过环境变量管理（参见 [`.env.example`](.env.example)）：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `APP_PORT` | 服务端口 | `8000` |
| `LOG_LEVEL` | 日志级别 | `info` |
| `LLM_PRIMARY_*` | 主模型配置 | minimax-m21 |
| `LLM_PRIMARY_THINKING_ENABLED` | Kimi K2.5 思考模式开关 | `true` |
| `LLM_FALLBACK_*` | 备用模型配置 | kimi-k2 |
| `VL_MODEL_URL` | VL 质量检查模型地址 | — |
| `LANGFUSE_*` | Langfuse 可观测性 | — |
| `IMAGE_*` | 图片上传目标 | — |
| `RENDER_OUTPUT_DIR` | 渲染临时目录 | `/tmp/image_gen` |

## 许可证

MIT
