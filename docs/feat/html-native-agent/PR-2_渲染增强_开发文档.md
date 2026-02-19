# PR-2：渲染增强（enhanced_web + ECharts）— 开发文档

**日期**: 2026-02-19
**状态**: 已完成
**依赖**: PR-1（HTML Native 化）

---

## 1. 目标

在 HTML Native Agent 基础上，让渲染器支持受控的 JavaScript 执行和 ECharts 图表库，使 Agent 能生成包含真实数据可视化图表的现代化页面（Dashboard、数据报告等），同时保持安全边界。

## 2. 核心设计

### 2.1 双模式渲染器

| 模式 | 触发条件 | 行为 |
|---|---|---|
| `pure_css` | HTML 不含 `<script>`/`echarts`/`__LUMI_RENDER_DONE__` | `networkidle` + 800ms 固定等待（兼容旧行为） |
| `enhanced_web` | HTML 包含 JS/ECharts 特征 | `domcontentloaded` + ready 信号等待 + 白名单网络拦截 |

**自动检测**：当 `render_html_mode=enhanced_web` 时，渲染器通过 `_detect_enhanced_content()` 启发式分析 HTML 内容，自动选择模式。纯 CSS 页面不会被误触发增强模式。

### 2.2 就绪信号协议

ECharts 页面必须在所有图表渲染完成后设置 `window.__LUMI_RENDER_DONE__ = true`。

等待策略（三级降级）：
1. **首选**：`page.wait_for_function("() => window.__LUMI_RENDER_DONE__ === true")`，超时 12s
2. **二级兜底**：等待 `canvas` / `svg` 选择器出现，超时 5s
3. **最终兜底**：固定等待 2000ms

### 2.3 网络白名单

通过 Playwright `page.route("**/*")` 拦截所有请求：
- **放行**：`data:`/`blob:`/`about:` URL、无 host 的同源请求、白名单域名
- **本地注入**：当 `render_use_local_echarts=true` 时，拦截 ECharts CDN 请求并返回本地 bundle
- **阻断**：外部图片（可配置）
- **放行但记录**：其他未白名单资源（记录日志用于排查）

### 2.4 本地 ECharts Bundle 兜底

`app/static/echarts.min.js`（1MB，ECharts v5）：
- 首次使用时加载到内存并缓存
- 通过 `page.route` 拦截 CDN URL 并用 `route.fulfill()` 返回本地内容
- 适用于网络受限的部署环境

---

## 3. 变更文件清单

| 文件 | 变更类型 | 说明 |
|---|---|---|
| `app/config.py` | 修改 | 新增 5 个渲染增强配置项 |
| `.env.example` | 修改 | 新增对应环境变量说明 |
| `app/util/renderer.py` | **重写** | 双模式渲染、ready 信号、网络白名单、本地 bundle 注入、结构化 error_code |
| `app/tool/html_render.py` | 修改 | 更新 docstring 说明 ECharts 支持 |
| `app/agent/prompt.py` | **重写** | 放开 ECharts 约束、新增 ECharts 编写规范和页面模板 |
| `app/static/echarts.min.js` | **新增** | ECharts v5 本地 bundle（1MB） |

### 3.1 新增配置项（`app/config.py`）

| 配置项 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `render_html_mode` | str | `enhanced_web` | 渲染模式：`pure_css` / `enhanced_web` |
| `render_allowed_hosts` | str | `cdn.jsdelivr.net,unpkg.com,cdnjs.cloudflare.com` | 白名单域名（逗号分隔） |
| `render_ready_timeout_ms` | int | `12000` | ready 信号等待超时（毫秒） |
| `render_block_external_images` | bool | `True` | 是否阻断外部图片请求 |
| `render_use_local_echarts` | bool | `False` | 是否使用本地 ECharts bundle |

### 3.2 新增文件

- `app/static/echarts.min.js` — Apache ECharts v5 完整 bundle

---

## 4. Prompt 变更要点

### 4.1 放开的约束

| PR-1 约束 | PR-2 变更 |
|---|---|
| 严禁依赖任何外部 JS 库 | **仅允许 ECharts**，通过 jsdelivr CDN 引入 |
| 严禁使用 JavaScript | 允许用于 ECharts 初始化和数据绑定 |
| 图表用纯 CSS 实现 | 纯 CSS 作为无图表场景的替代方案 |

### 4.2 新增 ECharts 编写规范

- 引入方式：`<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>`
- 容器必须有明确宽高
- 必须设置 `window.__LUMI_RENDER_DONE__ = true`
- 提供了完整的 ECharts 页面模板

---

## 5. 验证结果

### 5.1 CDN 可达性

```
CDN reachable! Status: 200  Size: 1034102 bytes
```

### 5.2 渲染测试

| 测试用例 | 模式 | 结果 | 文件大小 |
|---|---|---|---|
| 纯 CSS 卡片 | `pure_css`（自动检测） | ✅ success | ~8KB |
| 单图表（柱状图+折线图）| `enhanced_web` CDN | ✅ success | 19.6KB |
| 饼图（本地 bundle） | `enhanced_web` local | ✅ success | 10.2KB |
| 多图表 Dashboard（4 KPI + 柱状 + 饼图）| `enhanced_web` CDN | ✅ success | 32.5KB |

### 5.3 自动检测准确性

| 输入 | 检测结果 | 预期 |
|---|---|---|
| `<html><body><div>Hello</div></body></html>` | `False` | ✅ 纯 CSS |
| `<script src="echarts.min.js"></script>` | `True` | ✅ ECharts |
| `window.__LUMI_RENDER_DONE__` | `True` | ✅ 有 ready 信号 |

### 5.4 服务集成

```
ImageGenAgenticService initialized: OK
extract_image_url: OK
```

---

## 6. 配置级回滚

| 场景 | 操作 |
|---|---|
| ECharts 渲染不稳定 | 设置 `RENDER_HTML_MODE=pure_css` + 重启 → 回退纯 CSS 模式 |
| CDN 不可达 | 设置 `RENDER_USE_LOCAL_ECHARTS=true` + 重启 → 使用本地 bundle |
| 代码级回滚 | `git revert <this-commit>` |

---

## 7. 后续步骤

- **PR-3**：前端设计导向 Agent V1（DesignPlanner + VisualCritic）
- **PR-4**：质量门控 + Langfuse 指标 + 文档收口
