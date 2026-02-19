# HTML Native Agent 与前端设计导向机制完整开发方案（2026-02-18）

## 1. 目标与范围

### 1.1 目标
按两个大阶段推进：
1. 移除 Mermaid 工具链，将服务改为纯 HTML Native Agent。
2. 在 HTML Native 基础上实现“前端设计导向”的 Agent 机制，提升页面复杂度、现代感与稳定性。

### 1.2 非目标
- 本方案不新增扩散模型出图能力。
- 本方案不引入新的独立后端服务（保持当前 FastAPI + LangGraph 单服务架构）。
- 第一阶段不改变对外 API 路径（`/api/v1/conversations/*` 维持不变）。

---

## 2. 现状基线（与本次改造直接相关）

当前 Mermaid 相关耦合点：
- 工具导出：`app/tool/__init__.py`
- 工具实现：`app/tool/mermaid_render.py`
- 渲染引擎：`app/util/renderer.py` 中 `render_mermaid_to_image`
- Agent 工具注册：`app/agent/service.py`
- Agent 提示词策略：`app/agent/prompt.py`
- 配置项：`app/config.py` 中 `mermaid_cdn_url` 与 `.env.example`
- 文档描述：`README.md`、`README_CN.md`、`app/main.py` 描述文本

结论：移除 Mermaid 不是只删一个工具，需要一次“工具层 + agent层 + renderer层 + 文档层”的联动变更。

---

## 3. 总体实施策略

采用 4 个 PR 分步落地，降低风险：
1. PR-1：HTML Native 化（兼容迁移）
2. PR-2：前端设计导向 Agent 基础闭环（规划-生成-审稿）
3. PR-3：渲染增强（受控 JS / ECharts / Tailwind）
4. PR-4：质量与观测（指标、基准集、strict 模式）

每个 PR 都要求可独立回滚。

---

## 4. 第一阶段：移除 Mermaid，改为 HTML Native Agent

## 4.1 Step 1 - 引入迁移开关（1 天）
目标：避免直接硬切导致线上中断。

### 改动
- `app/config.py` 增加：
  - `agent_enable_mermaid: bool = False`（默认关闭）
- `.env.example` 增加同名配置说明。

### 行为
- 默认 Mermaid 不可用。
- 如需应急，可临时开启（仅用于迁移窗口）。

### 验收
- 关闭开关时，Agent 不注册 Mermaid 工具。
- 开启开关时可恢复旧路径。

## 4.2 Step 2 - Agent 工具表 HTML-only（1 天）

### 改动
- `app/agent/service.py`
  - `tools` 由 `[generate_html_image, generate_mermaid_image, check_image_quality]`
    改为 `[generate_html_image, check_image_quality]`
  - Mermaid 相关 import 改为按开关条件注入（迁移期）或直接删除（切换完成后）。

### 验收
- 日志中 tools 列表不包含 `generate_mermaid_image`。
- 流程图/时序图类请求仍能生成结果（通过 HTML 方案实现）。

## 4.3 Step 3 - 提示词改造为 HTML Native（1 天）

### 改动
- `app/agent/prompt.py`
  - 移除 Mermaid 工具说明、Mermaid 选择分支、Mermaid 编写规范。
  - 将所有图形需求统一引导为 HTML 生成（流程图、时序图、ER、架构图均走 HTML/CSS/SVG/Canvas/ECharts）。
  - 新增“图类页面结构模板规范”：节点层次、连线表现、图例、注释、标题区。

### 验收
- Prompt 中不再出现 `generate_mermaid_image`。
- Agent 对“画流程图”请求只调用 `generate_html_image`。

## 4.4 Step 4 - 删除 Mermaid 代码路径（1-2 天）

### 改动
- 删除文件：`app/tool/mermaid_render.py`
- `app/tool/__init__.py` 删除 Mermaid 导出。
- `app/util/renderer.py` 删除 `render_mermaid_to_image`。
- `app/util/__init__.py` 删除 Mermaid 导出。
- `app/config.py` 删除 `mermaid_cdn_url`。
- `.env.example` 删除 `MERMAID_CDN_URL`。

### 验收
- 全仓库 `rg mermaid` 仅剩历史文档（或明确保留说明），业务代码无 Mermaid 依赖。
- 服务可正常启动并通过 smoke test。

## 4.5 Step 5 - 文档与描述清理（0.5 天）

### 改动
- `README.md`、`README_CN.md`、`app/main.py` 文案由“HTML + Mermaid”改为“HTML Native”。
- `app/tool/image_qa.py` 注释中去掉对 Mermaid 工具的引用。

### 验收
- 对外文档与系统行为一致，无过时描述。

## 4.6 第一阶段测试清单

1. 单元测试
- `tests/test_service.py`：验证工具调用路径不再包含 Mermaid。
- `extract_image_url` 用例保持通过。

2. 集成测试
- 场景 A：流程图请求（原 Mermaid 强项）
- 场景 B：时序图请求
- 场景 C：架构图请求
要求：均可返回可读图，不报工具缺失。

3. 回归测试
- 多轮编辑能力（保持现有会话行为）。
- 质量检查链路（`check_image_quality`）保持调用。

---

## 5. 第二阶段：实现前端设计导向 Agent 机制

## 5.1 设计原则
- 先“可控结构化”，再“视觉美化”。
- 先“静态规则门控”，再“VL 视觉评分”。
- 先“模板提升成功率”，再“自由生成提升上限”。

## 5.2 目标架构（建议）

在当前 `ImageGenAgenticService` 内实现轻量多角色流程（不拆进程）：
1. `DesignPlanner`：把用户需求转成 `design_spec`（JSON）。
2. `HtmlComposer`：根据 `design_spec` 生成 HTML。
3. `RenderExecutor`：调用 `generate_html_image` 渲染。
4. `VisualCritic`：规则检查 + `check_image_quality`。
5. `RepairLoop`：失败时按建议修复，最多 2 轮。

## 5.3 新增数据契约

新增 `design_spec` 结构（建议独立 schema）：
- `page_type`: `dashboard|infographic|landing|report|diagram`
- `layout`: 区块定义（header/main/sidebar/footer + grid）
- `sections[]`: 每个 section 的类型与内容目标
- `visual_tokens`: 颜色、字体、圆角、阴影、间距、密度
- `chart_plan[]`: 图表类型、数据字段、配色规则
- `constraints`: 响应式、可读性、最大宽度、最小字号

建议新增文件：
- `app/agent/frontend_design/spec_schema.py`
- `app/agent/frontend_design/rules.py`
- `app/agent/frontend_design/templates.py`

## 5.4 Prompt 分层方案

### A. 系统主提示词
- 明确“必须输出现代化、高层次页面结构”。
- 明确“避免初学者风格（单列堆叠、默认系统样式、无层次配色）”。

### B. 角色提示词
- `DesignPlanner Prompt`：只产出结构化规格，不产出 HTML。
- `HtmlComposer Prompt`：严格消费规格生成 HTML。
- `VisualCritic Prompt`：只输出问题与修复建议。

### C. 失败重试策略
- 第一次失败：仅局部修复。
- 第二次失败：允许重排布局。
- 第三次失败：返回最佳可用结果并附简短说明。

## 5.5 渲染能力增强（支撑复杂现代页面）

### 目标
让 HTML Agent 能真正画出“现代前端页面”，而非纯静态卡片。

### 改动建议
- `app/util/renderer.py`
  - 新增 `enhanced_web` 模式：允许受控 JS。
  - 增加 ready 信号：`window.__LUMI_RENDER_DONE__`。
  - 增加请求白名单拦截（只允许配置域名）。

- `app/config.py`
  - 新增：`render_html_mode`、`render_allowed_hosts`、`render_ready_timeout_ms`。

- `app/tool/html_render.py`
  - 新增可选参数：`render_profile`、`allow_libraries`。

### 库策略
- ECharts：优先支持（现代数据可视化核心能力）。
- Tailwind：建议“预编译 CSS 本地化”为主，CDN 为辅（调试模式）。

## 5.6 质量门控机制（新增）

在 VL 之前增加静态规则检查器（低成本高稳定）：
- 结构复杂度：section/card/chart 数量是否达标。
- 视觉层次：字号层级 >= 3、主次色明确、留白合理。
- 内容完整性：禁止占位词（TODO、lorem ipsum、示例文本）。
- 可读性：最小字号阈值、对比度阈值。

新增模块建议：
- `app/tool/html_lint.py`（或 `app/agent/frontend_design/static_checks.py`）

## 5.7 API 扩展（可选但建议）

在 `app/api/schemas.py` 的 `ConversationMessageRequest` 增加可选字段：
- `render_mode`: `auto|pure_css|enhanced_web`
- `design_mode`: `auto|standard|frontend_pro`
- `quality_mode`: `relaxed|strict`

默认 `auto`，保证兼容当前客户端。

## 5.8 第二阶段测试清单

1. 单元测试
- `design_spec` 解析与校验。
- 静态规则检查器（正例/反例）。

2. 集成测试
- dashboard、数据报告、营销落地页、流程架构页各 5 条。
- 验证生成链路：Planner -> Composer -> Render -> Critic -> Retry。

3. 质量测试
- 一次通过率、平均重试次数、P95 时延、VL 平均分。

---

## 6. PR 切分与交付物

## PR-1（HTML Native）
交付：Mermaid 完整下线，HTML-only Agent 可用。

## PR-2（Design 机制 V1）
交付：DesignPlanner + HtmlComposer + VisualCritic 最小闭环。

## PR-3（Renderer 增强）
交付：enhanced_web + ready 协议 + 受控外链。

## PR-4（质量与指标）
交付：静态规则门控、strict 模式、Langfuse 指标维度。

---

## 7. 时间计划（建议 12 个工作日）

1. D1-D3：PR-1（HTML Native 化）
2. D4-D7：PR-2（Design Agent V1）
3. D8-D10：PR-3（渲染增强）
4. D11-D12：PR-4（质量门控 + 指标 + 文档收口）

---

## 8. 验收标准（最终）

1. 功能验收
- Agent 不再依赖 Mermaid 代码和工具。
- 复杂页面请求可稳定生成（dashboard/report/diagram）。

2. 质量验收
- 复杂页面一次通过率 >= 80%。
- VL 平均分 >= 8（阈值可按业务调整）。
- 空白图率 <= 2%。

3. 性能验收
- 端到端 P95 <= 15s（含质量检查）。

4. 维护性验收
- 新增模块有单元测试。
- README 与 API 文档同步更新。

---

## 9. 风险与回滚策略

1. 风险：Mermaid 下线后某些技术图退化
- 对策：第一阶段先保留 feature flag（可临时回开），并补 HTML 图模板。

2. 风险：设计导向流程增加时延
- 对策：限制重试次数；静态检查前置，减少无效 VL 调用。

3. 风险：外部库加载不稳定
- 对策：白名单 + 本地静态资源 + 超时兜底。

4. 回滚策略
- PR 级可回滚：按 PR-4 -> PR-3 -> PR-2 -> PR-1 逆序回退。
- 配置级快速兜底：切回 `pure_css` 与 `design_mode=standard`。

---

## 10. 执行建议（从今天开始）

1. 先执行 PR-1，把 Mermaid 从主链路彻底退出，但保留短期开关兜底。
2. 紧接 PR-2 上线前端设计导向最小闭环，不等待渲染增强全部完成。
3. PR-3/PR-4 并行推进，最终以“复杂页面基准集”数据作为上线门槛。

