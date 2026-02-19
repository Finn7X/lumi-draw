# HTML 现代网页渲染与设计 Agent 优化方案（2026-02-18）

## 1. 背景与目标

### 1.1 背景
当前 `lumi-draw` 的 HTML 出图能力被显式限制在“纯 HTML + CSS、禁用外部库、禁用 JavaScript”的模式，导致复杂现代页面（如有真实图表、现代组件体系、视觉层次）的生成上限较低。

仓库内可见的硬限制：
- `app/agent/prompt.py:55` 明确禁止外部 JS/CSS 库（包括 ECharts、Tailwind CDN）。
- `app/agent/prompt.py:56` 明确禁止 JavaScript。
- `app/util/renderer.py:115` 与 `app/util/renderer.py:140` 在错误提示中继续引导“仅纯 CSS”。

### 1.2 目标（对应你提出的两条方向）
1. 渲染能力升级：支持在 HTML 渲染阶段使用 ECharts、Tailwind 等高级库并稳定出图。
2. Agent 机制升级：引入“前端设计导向”的编排机制，让模型更稳定地产出复杂、现代、具审美层次的页面。

---

## 2. 外部调研结论（截至 2026-02-18）

### 2.1 ECharts 与浏览器渲染
- ECharts 官方示例支持通过 `<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>` 在浏览器直接渲染图表，并通过 `setOption` 完成绘制。
- ECharts 也提供 SSR（自 5.3.0 起支持字符串 SVG 的服务端渲染），可作为离线兜底路径。

结论：在 Playwright 截图链路中，ECharts 是可落地的；若担心网络或脚本执行不稳定，可追加 SSR 兜底。

### 2.2 Tailwind 使用方式
- Tailwind 文档提供 Play CDN 方式，但其定位更偏快速原型，不建议直接作为生产主路径。

结论：建议双模式：
- 快速模式：允许 Play CDN（用于研发验证/内部环境）。
- 生产模式：预编译 Tailwind CSS（本地静态文件），渲染时不依赖外网。

### 2.3 Playwright 渲染等待策略
- Playwright `setContent(..., waitUntil='networkidle')` 被官方标注为不推荐作为测试就绪判断。
- Playwright 提供 `page.route`/`route.abort` 等请求拦截机制，可做资源白名单控制。

结论：需要从“networkidle + 固定 sleep”升级为“应用级 ready 信号 + 选择器等待 + 网络白名单”。

### 2.4 “类似 frontend-design 插件/skill”的工程启发
- Claude Code 官方文档显示可通过 **sub-agents**（独立上下文）与 **hooks**（工具前后拦截）实现可组合工作流。

结论：可在当前 LangGraph 架构里复刻同类思想：拆分角色、分阶段产出、自动评审和重写闭环。

---

## 3. 方向一：HTML 渲染支持高级库（ECharts/Tailwind）

## 3.1 目标能力
- 支持 JS 执行与图表库渲染（ECharts、后续可扩展 Chart.js/D3）。
- 支持 Tailwind 风格化布局（CDN 或预编译 CSS）。
- 支持“渲染完成信号”后再截图，降低空白图与半成品图。
- 保留安全边界（外链白名单、资源超时、脚本约束）。

## 3.2 推荐架构（分层）

### A. Renderer 层改造（`app/util/renderer.py`）
1. 新增渲染模式：
- `pure_css`（兼容现状）
- `enhanced_web`（允许受控 JS/外部库）

2. 新增“就绪检测协议”：
- 页面 JS 渲染完成后设置 `window.__LUMI_RENDER_DONE__ = true`。
- Renderer 等待：
  - `page.wait_for_function("() => window.__LUMI_RENDER_DONE__ === true")`
  - 或兜底等待关键选择器（如 `#chart canvas`, `.echarts-for-react`, `[data-lumi-ready="1"]`）。

3. 替换等待策略：
- 当前 `networkidle` 改为 `domcontentloaded` + 自定义就绪信号。

4. 增加网络白名单：
- 用 `page.route("**/*")` 拦截请求，仅放行：
  - 文档本身
  - 白名单 CDN 域名（可配置）
  - 本地静态资源
- 默认阻断图片追踪像素、未知第三方脚本、跨域字体等。

5. 诊断增强：
- 输出失败请求列表（URL + 状态 + 资源类型）。
- 输出页面端 `console.error` 栈。
- 失败时返回结构化错误码（如 `LIB_LOAD_FAILED`, `READY_TIMEOUT`）。

### B. Config 层改造（`app/config.py` / `.env.example`）
建议新增：
- `render_html_mode=enhanced_web`
- `render_allow_javascript=true`
- `render_allowed_script_hosts=cdn.jsdelivr.net,unpkg.com`
- `render_allowed_style_hosts=cdn.jsdelivr.net,fonts.googleapis.com`
- `render_ready_timeout_ms=12000`
- `render_block_external_images=true`

### C. Tool 层改造（`app/tool/html_render.py`）
建议增加工具参数：
- `render_profile: str = "auto"`（`auto/dashboard/landing/report`）
- `allow_libraries: list[str] | None`（如 `['echarts','tailwind']`）

实现要点：
- 工具层只声明“可用库”与“渲染 profile”，实际权限仍由 renderer 白名单控制。

### D. Prompt 层改造（`app/agent/prompt.py`）
- 删除“禁止 JS/外部库”的硬禁令，改为“在受控白名单内可用”。
- 增加可复用代码规范：
  - ECharts 必须包含 `option` 完整定义。
  - 渲染结束必须设置 `window.__LUMI_RENDER_DONE__ = true`。
  - Tailwind 若使用 CDN，需在 head 正确引入并保证关键样式可见。

## 3.3 落地策略
- P0（最小可用）：只开 ECharts + 预设模板（柱状图/折线图/饼图）。
- P1：放开 Tailwind（优先预编译 CSS，本地文件）。
- P2：补充 SSR 兜底（ECharts SVG -> 再截图）。

## 3.4 验收标准
- 同一批 30 个复杂 Dashboard 用例：
  - 渲染成功率 >= 95%
  - 空白图率 <= 2%
  - 平均渲染时延（P50）<= 8s
- 至少 10 个用例真实使用 ECharts，且 VL 评分 >= 8。

---

## 4. 方向二：前端设计导向的 Agent 机制

## 4.1 目标能力
从“单次代码生成”升级为“设计-实现-评审”闭环，提升页面复杂度、审美一致性和稳定通过率。

## 4.2 推荐 Agent 工作流（LangGraph 可实现）

1. `DesignPlanner`（规划器）
- 输入用户需求。
- 输出结构化设计规格 JSON：
  - 信息架构（section/card/chart/table）
  - 视觉方向（颜色、字体、密度、留白）
  - 交互/动效约束（可选）

2. `LayoutComposer`（布局器）
- 将规格转为页面骨架（Grid/Flex、响应式断点、主次层级）。

3. `StyleEngineer`（样式工程师）
- 注入 design tokens（颜色、字号、阴影、圆角、间距）。
- 调用 Tailwind 或内联样式实现风格一致性。

4. `ChartEngineer`（图表工程师）
- 负责 ECharts 代码片段与数据映射。
- 保证图表可读性（坐标轴、图例、单位、标题）。

5. `VisualCritic`（视觉审稿）
- 结合 `check_image_quality` + 静态规则评估：
  - 可读性
  - 信息密度
  - 视觉层次
  - 与需求一致性
- 失败则返回明确修复指令，最多重试 N 次。

## 4.3 “类似插件/skill”的实现方式

### 方案 A（推荐）：内置子流程 + Prompt 套件
- 在当前服务内新增“前端设计模式”系统提示词模板和子任务拆解模板。
- 优点：部署简单，和现有 API 兼容。

### 方案 B：新增 `frontend-design` Skill 包
可在仓库新增 skill 目录（遵循 `skill-creator` 原则），包含：
- `SKILL.md`：触发条件、工作流、禁止项。
- `references/`：设计风格参考、图表规范。
- `assets/templates/`：可复用 HTML/ECharts 页面模板。
- `scripts/`：静态 lint（DOM 层级、对比度、留白密度、图表数量）。

建议：先做方案 A，稳定后沉淀为方案 B。

## 4.4 设计质量门控（新增）
在 `check_image_quality` 之前增加轻量静态检查：
- 结构复杂度：section/card/chart/table 数量阈值。
- 视觉复杂度：颜色 token 数量、字号层级数量、阴影/边框变化数量。
- 内容完整度：禁止占位词（如“TODO”“lorem ipsum”）。

这一步比 VL 更稳定，可减少“看起来像半成品”的输出。

## 4.5 多轮编辑能力增强
当前已有会话记忆，可新增“局部编辑协议”：
- 用户可指定“只改某区块/某图表”。
- Agent 返回 patch 目标（例如 `section_id=metrics-2`），避免整页重绘。

---

## 5. 接口与数据结构建议

## 5.1 API 入参扩展（`app/api/schemas.py`）
建议在 `ConversationMessageRequest` 增加可选字段：
- `render_mode`: `auto | pure_css | enhanced_web`
- `design_mode`: `auto | standard | frontend_pro`
- `quality_mode`: `relaxed | strict`

默认保持 `auto`，兼容现有调用。

## 5.2 可观测性（Langfuse）
新增埋点维度：
- `render_mode`
- `libraries_used`
- `retry_count`
- `quality_score`
- `ready_wait_ms`

用于比较升级前后效果。

---

## 6. 实施计划（建议 3 周）

## 第 1 周：渲染能力最小闭环
1. Renderer 支持 `enhanced_web` 与 ready 信号。
2. 放开 ECharts 白名单。
3. Prompt 改造 + 10 条回归用例。

## 第 2 周：设计 Agent 闭环
1. 引入 DesignPlanner/VisualCritic 子流程。
2. 新增静态规则检查器。
3. 建立复杂页面基准集（30 条）。

## 第 3 周：稳定性与产品化
1. Tailwind 预编译方案接入。
2. 严格模式开关（strict quality）。
3. 指标看板与压测。

---

## 7. 风险与对策

1. 外部 CDN 不稳定
- 对策：白名单 + 本地静态镜像 + SSR 兜底。

2. JS 增加攻击面
- 对策：请求拦截、域名白名单、资源大小/超时限制、禁用未知外链。

3. Agent 复杂度上升导致时延增加
- 对策：限制重试轮数；将静态检查前置，减少无效 VL 调用。

4. 视觉质量仍不稳定
- 对策：模板优先、风格 token 化、失败回退到高成功率模板。

---

## 8. 最终建议（执行优先级）

1. 先打通方向一（ECharts + ready 信号 + 白名单网络）作为能力底座。
2. 再实现方向二中的最小闭环（规划器 + 审稿器 + 重试）。
3. 最后沉淀为 `frontend-design` skill（模板化、可复用、可持续迭代）。

---

## 9. 参考资料（官方一手）

- Apache ECharts Handbook（浏览器引入与 `setOption`）：
  https://echarts.apache.org/handbook/en/get-started/
- Apache ECharts SSR Handbook（服务端渲染能力）：
  https://echarts.apache.org/handbook/en/how-to/cross-platform/server/
- Tailwind CSS（安装与 Play CDN 入口）：
  https://tailwindcss.com/docs/installation/tailwind-cli
  https://tailwindcss.com/docs/installation/play-cdn
- Playwright API（`setContent` / `waitUntil` 说明）：
  https://playwright.dev/docs/api/class-frame
- Playwright 网络拦截（`route` / `abort`）：
  https://playwright.dev/docs/network
- Anthropic Claude Code（sub-agents）：
  https://docs.anthropic.com/en/docs/claude-code/sub-agents
- Anthropic Claude Code（hooks）：
  https://docs.anthropic.com/en/docs/claude-code/hooks

