<div align="center">

# Lumi Draw

### 不用生图模型，也能生成图片

**用 LLM 写代码代替像素生成 —— 结构化视觉内容的全新范式**

[English](README.md) · [快速开始](#-快速开始) · [案例展示](#-案例展示) · [架构设计](#-架构设计)

</div>

---

## 为什么需要 Lumi Draw？

DALL-E、Midjourney、Stable Diffusion 在生成"艺术图片"上表现出色，但面对**结构化视觉内容**时力不从心：

| 痛点 | 传统生图模型 | Lumi Draw |
|------|-------------|-----------|
| 布局控制 | Prompt 反复试错，难以精确控制元素位置 | HTML/CSS 像素级精确布局 |
| 文字渲染 | 经常出现乱码、错字、模糊 | 浏览器原生渲染，字体完美清晰 |
| 数据图表 | 无法生成真实数据的图表 | ECharts 渲染真实数据可视化 |
| 迭代修改 | 每次都要从头重新生成 | 多轮对话增量编辑，改哪说哪 |
| 可复现性 | 同一 Prompt 每次结果不同 | 同一代码每次渲染结果完全一致 |
| 部署成本 | 需要 GPU + 模型推理服务 | 只需 LLM API + 无头浏览器 |

**核心洞察**：流程图、数据仪表盘、社交媒体卡片、信息长图、排版模板…… 这些结构化内容的本质是**代码**，而非像素。让 LLM 写代码，再用浏览器渲染成图片，是更自然也更可控的路径。

---

## 🎯 案例展示

### Case 1：小红书排版 → 多轮迭代修改

> **第 1 轮**：`绘制简单的小红书排版示意图`
> **第 2 轮**：`使用苹果手机作为示例，移除原本的背景，只保留手机部分`

Agent 先生成完整的小红书界面布局，第二轮基于已有代码增量修改 —— 将布局嵌入 iPhone 设备框中并移除背景，无需从零重来。

<p align="center">
  <img src="demo/case1.png" alt="Case 1 - 小红书排版多轮迭代" width="600" />
</p>

### Case 2：SaaS 管理后台 Dashboard

> **第 1 轮**：`开发简单的SaaS智能后台管理型Dashboard页面`
> **第 2 轮**：`开发简单的深色调专业高级SaaS智能后台Dashboard页面`

Agent 一次性生成包含侧边栏导航、KPI 指标卡、折线图、饼图、柱状图的完整 Dashboard，数据、配色、布局全部到位。第二轮切换深色主题，精准调整。

<p align="center">
  <img src="demo/case2.png" alt="Case 2 - SaaS Dashboard 数据可视化" width="600" />
</p>

---

## 🏗 架构设计

```
用户输入 (自然语言)
    │
    ▼
┌─────────────────────────────────┐
│  LangGraph Agent                │
│  ┌───────────────────────────┐  │
│  │ System Prompt (生图专家)   │  │
│  │ + 虚拟文件系统 (VFS)       │  │
│  │ + 中间件栈                 │  │
│  └───────────────────────────┘  │
│            │                    │
│   ┌───────┴────────┐           │
│   ▼                ▼           │
│ 简单任务        复杂/多轮任务    │
│ 直接生成HTML    VFS写入+渲染    │
│   │                │           │
│   └───────┬────────┘           │
│           ▼                    │
│  Playwright 无头浏览器渲染       │
│           │                    │
│           ▼                    │
│  VL 模型质量评估 (Qwen3-VL)     │
│  得分 < 7? → 自动修复重试       │
│           │                    │
│           ▼                    │
│     输出最终 PNG 图片           │
└─────────────────────────────────┘
```

### 关键技术创新

- **HTML Native Agent**：跳过 Mermaid/SVG 等中间层，LLM 直接生成 HTML/CSS/JS，Playwright 渲染截图。消除了转换损耗，释放了全部 Web 表现力。

- **双模式渲染引擎**：`pure_css` 纯静态模式 + `enhanced_web` 动态模式（支持 ECharts 图表），通过 `window.__LUMI_RENDER_DONE__` 信号精确控制截图时机。

- **VL 质量闭环**：渲染后自动调用视觉语言模型 (Qwen3-VL) 从完整性、可读性、视觉质量、准确性四维评分，不合格则 Agent 自主修复并重试（最多 2 次）。

- **虚拟文件系统 (VFS)**：内存级文件系统支持 `write_file` / `edit_file` / `read_file`，多轮对话间保持代码状态，实现真正的增量编辑。

- **智能中间件栈**：上下文自动压缩（50k token 清理旧工具输出）、会话摘要（90k token 触发）、模型自动降级、Kimi thinking 兼容修复，保障长对话稳定性。

---

## 🚀 快速开始

### 本地开发

```bash
# 1. 克隆项目
git clone https://github.com/your-username/lumi-draw.git
cd lumi-draw

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 LLM API 配置

# 3. 安装依赖
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# 4. 启动后端 (端口 7700)
uvicorn app.main:app --host 0.0.0.0 --port 7700

# 5. 新终端启动前端 (端口 7800)
python3 frontend/serve.py
```

打开浏览器访问 `http://localhost:7800/`

### Docker 一键部署

```bash
cp .env.example .env
# 编辑 .env 填入配置
docker compose up -d --build
```

访问 `http://localhost:7800/`

---

## 📡 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/conversations` | 创建会话 |
| POST | `/api/v1/conversations/{id}/messages` | 发送消息（生成图片） |
| GET | `/api/v1/conversations/{id}/messages` | 获取会话历史 |
| GET | `/api/v1/health` | 健康检查 |

**示例：多轮迭代生图**

```bash
# 创建会话
CID=$(curl -s http://localhost:7700/api/v1/conversations \
  -X POST -H 'Content-Type: application/json' -d '{}' | jq -r '.conversation_id')

# 第一轮：生成 Dashboard
curl -s http://localhost:7700/api/v1/conversations/$CID/messages \
  -X POST -H 'Content-Type: application/json' \
  -d '{"query":"生成一个SaaS管理后台Dashboard，包含用户数、收入、订单等指标"}'

# 第二轮：切换深色主题
curl -s http://localhost:7700/api/v1/conversations/$CID/messages \
  -X POST -H 'Content-Type: application/json' \
  -d '{"query":"切换为深色主题，优化配色"}'
```

---

## ⚙️ 核心配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_PRIMARY_MODEL` | 主 LLM 模型 | `minimax-m21` |
| `LLM_PRIMARY_BASE_URL` | 主模型 API 地址 | - |
| `LLM_PRIMARY_API_KEY` | 主模型 API Key | - |
| `LLM_PRIMARY_THINKING_ENABLED` | 启用 thinking 模式 | `true` |
| `LLM_PRIMARY_TIMEOUT` | 模型超时（秒） | `600` |
| `VL_MODEL_URL` | 视觉质量检查模型地址 | - |
| `VL_QUALITY_THRESHOLD` | 质量评分阈值 (0-10) | `7` |
| `RENDER_HTML_MODE` | 渲染模式 | `enhanced_web` |
| `AGENT_ENABLE_VIRTUAL_FILESYSTEM` | 启用虚拟文件系统 | `true` |
| `LANGFUSE_HOST` | Langfuse 追踪地址 | - |

完整配置见 [.env.example](.env.example)。

---

## 🆚 与同类项目对比

| 特性 | Lumi Draw | Diffusion 生图 | 截图工具 |
|------|-----------|---------------|---------|
| 结构化布局控制 | ✅ 像素级精确 | ❌ 概率性输出 | ❌ 需要手动设计 |
| 中文文字渲染 | ✅ 完美清晰 | ❌ 常有乱码 | ✅ |
| 数据图表生成 | ✅ ECharts 真实数据 | ❌ 不支持 | ❌ 需手动制作 |
| 多轮迭代编辑 | ✅ 增量修改 | ❌ 重新生成 | ❌ |
| 自动质量检查 | ✅ VL 模型闭环 | ❌ | ❌ |
| GPU 依赖 | ❌ 无需 GPU | ✅ 需要 GPU | ❌ |
| 可观测性 | ✅ Langfuse 全链路 | ❌ | ❌ |

---

## 🤝 参与贡献

欢迎提交 Issue 和 Pull Request。

## 📄 License

[MIT](LICENSE)
