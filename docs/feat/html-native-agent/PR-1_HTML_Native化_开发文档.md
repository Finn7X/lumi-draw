# PR-1：HTML Native 化 — 开发文档

**日期**: 2026-02-19
**状态**: 已完成

---

## 1. 目标

移除 Mermaid 工具链，将服务改为纯 HTML Native Agent。所有图片生成（包括流程图、时序图、架构图等原 Mermaid 强项场景）统一走 HTML/CSS/SVG 渲染路径。

## 2. 变更范围

### 2.1 变更文件清单

| 文件 | 变更类型 | 说明 |
|---|---|---|
| `app/config.py` | 修改 | 新增 `agent_enable_mermaid` flag；删除 `mermaid_cdn_url` 字段；增加 `extra="ignore"` 防止 `.env` 残留字段报错 |
| `.env.example` | 修改 | 新增 `AGENT_ENABLE_MERMAID=false`；删除 `MERMAID_CDN_URL` |
| `app/agent/service.py` | 修改 | 默认 tools 仅含 HTML + VL；Mermaid 工具改为按 flag 条件动态注入（ImportError 安全）；更新模块和类 docstring |
| `app/agent/prompt.py` | 重写 | 删除全部 Mermaid 工具说明、选择规则、编写规范；新增 HTML 流程图/架构图绘制指导（SVG/CSS 节点连线） |
| `app/tool/mermaid_render.py` | **删除** | Mermaid 渲染工具完整移除 |
| `app/tool/__init__.py` | 修改 | 删除 `generate_mermaid_image` 导入和导出 |
| `app/util/renderer.py` | 修改 | 删除 `render_mermaid_to_image` 函数（~100行）；更新模块 docstring |
| `app/util/__init__.py` | 修改 | 删除 `render_mermaid_to_image` 导出 |
| `app/main.py` | 修改 | FastAPI description 由 "HTML and Mermaid" 改为 "HTML Native" |
| `app/tool/image_qa.py` | 修改 | docstring 删除对 `generate_mermaid_image` 的引用 |
| `README.md` | 修改 | 描述、架构图、项目结构移除 Mermaid 相关内容 |
| `README_CN.md` | 修改 | 同上（中文版） |

### 2.2 已删除文件

- `app/tool/mermaid_render.py`

### 2.3 未变更的关键文件

- `app/tool/html_render.py` — 无需修改
- `app/util/uploader.py` — 无需修改
- `app/api/routes.py`、`app/api/schemas.py` — API 接口无变更
- `tests/test_service.py` — 现有测试兼容（`extract_image_url` 不依赖 Mermaid）

---

## 3. 设计决策

### 3.1 Feature Flag 机制

新增 `agent_enable_mermaid: bool = False`（`app/config.py:65`）：
- 默认关闭，Agent 只注册 `generate_html_image` + `check_image_quality`
- 开启时，`service.py` 尝试动态 import `generate_mermaid_image`，import 失败会 warning 而非崩溃
- **限制**：由于 `@lru_cache` 机制，此 flag 仅在服务重启时生效，无法运行时热切换
- **注意**：Mermaid 代码文件已删除，开启 flag 会触发 ImportError warning。真正回滚需 git revert

### 3.2 Pydantic `extra="ignore"` 防护

`model_config` 新增 `"extra": "ignore"`，确保用户现有 `.env` 文件中的 `MERMAID_CDN_URL` 不会因为 Settings 模型删除该字段而导致启动 ValidationError。这是一个向前兼容的防护措施。

### 3.3 Prompt 新增 HTML 图表绘制指导

原 Mermaid 处理的流程图、时序图、架构图场景，现在需要通过 HTML/CSS/SVG 实现。prompt 新增了具体指导：
- 节点：`div` + `border` + `border-radius`
- 连线：CSS 伪元素或内联 SVG `<line>`/`<path>`
- 箭头：CSS border 三角形或 SVG `<marker>`
- 布局：CSS Grid/Flexbox 控制节点位置

---

## 4. 验证结果

### 4.1 模块导入验证

| 检查项 | 结果 |
|---|---|
| `from app.config import get_settings` | ✅ 正常，`agent_enable_mermaid=False` |
| `from app.tool import generate_html_image, check_image_quality` | ✅ 正常 |
| `from app.tool import generate_mermaid_image` | ✅ 抛出 `ImportError`（预期行为） |
| `from app.util.renderer import render_html_to_image` | ✅ 正常 |
| `from app.util.renderer import render_mermaid_to_image` | ✅ 抛出 `ImportError`（预期行为） |

### 4.2 服务初始化验证

```
ImageGenAgenticService(service_name='test_pr1') → Service initialized OK
```

### 4.3 单元测试验证

```
extract_image_url("...![流程图](http://example.com/abc.png)") → "http://example.com/abc.png" ✅
extract_image_url("no image here") → None ✅
```

### 4.4 Mermaid 残留扫描

`rg -i mermaid app/` 结果仅包含：
- `app/config.py` — flag 注释和字段定义（预期保留）
- `app/agent/service.py` — flag 条件分支（预期保留）

其余业务代码、工具、渲染器、提示词中无任何 Mermaid 引用。

---

## 5. 兼容性说明

### 5.1 对外 API 无变更

- `POST /api/v1/generate` 请求/响应格式不变
- `POST /api/v1/conversations/{id}/messages` 不变
- `GET /api/v1/health` 不变

### 5.2 现有 `.env` 文件兼容

用户现有 `.env` 中的 `MERMAID_CDN_URL=...` 不会导致启动失败（`extra="ignore"` 防护）。

### 5.3 行为变化

| 场景 | 变更前 | 变更后 |
|---|---|---|
| "画一个用户登录流程图" | Agent 可能选 Mermaid 或 HTML | 只走 HTML，用 CSS/SVG 绘制 |
| "画时序图" | Agent 选 Mermaid | 只走 HTML，用 CSS/SVG 绘制 |
| Dashboard/仪表盘/数据卡片 | HTML | HTML（不变） |
| 多轮编辑 | 不变 | 不变 |
| VL 质量检查 | 不变 | 不变 |

---

## 6. 回滚策略

- **配置级**：设置 `AGENT_ENABLE_MERMAID=true` + 重启（但由于 Mermaid 代码已删除，会触发 ImportError warning，Agent 仍以 HTML-only 模式运行）
- **代码级**：`git revert <this-commit>` 可完整恢复 Mermaid 工具链

---

## 7. 后续步骤

本 PR 完成后，按最终方案推进：
- **PR-2**：Renderer 增强（`enhanced_web` 模式 + ECharts + ready 信号 + 白名单）
- **PR-3**：前端设计导向 Agent V1（DesignPlanner + VisualCritic）
- **PR-4**：质量门控 + Langfuse 指标 + 文档收口
