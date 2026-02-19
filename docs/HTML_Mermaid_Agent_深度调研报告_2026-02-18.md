# HTML/Mermaid 图像生成 Agent 深度调研报告（2026-02-18）

## 1. 执行摘要
你的项目（`lumi-draw`）采用“LLM 产出结构化代码（HTML/Mermaid）+ 确定性渲染（Playwright）+ 质量校验（VL）”路线，本质上是**程序化制图 Agent**，而非扩散模型式图像生成器。  
这条路线的核心价值是：可控、可复现、可审计、可编辑、低幻觉成本，尤其适合流程图、架构图、业务图、信息卡片和报告配图。

综合调研结论：该 Agent 的商业与工程价值是明确的，但要形成差异化，不应停留在“自然语言 -> 一次性出图”，而应升级为“**图文档生产系统**”：支持多引擎、可迭代编辑、模板资产、质量评测与团队协作链路。

---

## 2. 你的 Agent 的意义与价值

### 2.1 为什么这条路线成立
- 相比扩散模型，HTML/Mermaid 方案对结构化信息表达更稳定，文本可读性更好。
- Mermaid、Graphviz、PlantUML、D2 都是“文本即图”的成熟范式，生态稳定，便于嵌入 CI/CD 与文档流程。
- Playwright 截图能力成熟，天然适合将 HTML/CSS 或浏览器渲染结果转为图片产物。

### 2.2 你的现有实现优势（结合仓库）
- 工具链完整：`generate_html_image` + `generate_mermaid_image` + `check_image_quality`。
- Agent 编排完善：有 fallback、summarization、tool-call patch、context editing。
- 工程化到位：FastAPI API、Docker Compose、可上传产物、具备健康检查。

### 2.3 当前短板（关键）
- 交互单轮：缺少“局部修改/增量编辑”能力，用户需重复描述。
- 质量门控偏弱：VL 检查为 fail-open，模型不可用时默认放行，线上质量风险高。
- 渲染引擎单一：目前主要 HTML/Mermaid，复杂架构图和工程图覆盖仍有限。
- 评测体系不足：缺少标准化 benchmark（成功率、可读性、返工率、时延/成本）。

---

## 3. 同类型 Agent/Skills 与解决思路

| 类别 | 代表方案 | 如何解决“无图像模型生成图片” | 适用场景 | 局限 |
|---|---|---|---|---|
| 通用浏览器渲染型 Skill | OpenAI `playwright`、`screenshot` | 通过浏览器自动化执行页面/截图生成视觉结果 | 网页、报告快照、UI/文档截图 | 不是专门制图 DSL，结构语义弱 |
| 图像模型型 Skill（对照组） | OpenAI `imagegen` | 直接调用图像模型生成图片 | 创意图、风格图 | 可控性/可编辑性较弱，文本结构图易失真 |
| 文本图表 DSL | Mermaid | LLM 生成 Mermaid 代码，再渲染为 SVG/PNG | 流程图、时序图、架构草图 | 对自由排版和视觉细节控制有限 |
| UML/工程图 DSL | PlantUML | 文本描述 UML/时序/状态图后端渲染 | 软件工程文档、UML 规范图 | 语法较重，审美默认风格偏工程 |
| 图布局引擎 | Graphviz(DOT) | 节点/边 + 自动布局输出图形 | 拓扑图、依赖图、关系图 | 需较强结构建模能力 |
| 新一代 Diagram-as-code | D2 | 声明式图描述 + 自动布局与导出 | 架构/系统设计图 | 生态规模仍小于 Mermaid/PlantUML |
| 多引擎聚合服务 | Kroki | 一个 API 聚合多种 DSL 渲染 | 平台化制图服务 | 需治理安全、性能与依赖维护 |
| 架构建模导向 | Structurizr DSL | C4 模型先建模再生成多视图 | 企业架构治理、文档一致性 | 学习门槛高，前期建模成本高 |

结论：你的路线最接近“Mermaid/PlantUML/Kroki + Agent 编排”这一类；如果做深，壁垒在**工作流与数据资产**，不在“单次出图”。

---

## 4. 应用场景评估（按价值密度）

### 4.1 高价值场景（优先）
- 研发文档即图：需求评审、架构评审、事故复盘、接口/流程说明。
- 业务流程可视化：运营 SOP、审批流、客服流程、风控规则链路。
- 报告自动配图：将结构化数据/结论自动转成信息图卡片。

### 4.2 中价值场景
- 教学课件配图与知识图谱。
- 内部系统说明图自动生成（Onboarding 文档）。

### 4.3 低匹配场景
- 写实海报、插画、营销创意图（更适合扩散模型）。

---

## 5. 后续应添加的功能（从“工具”到“产品”）

### 5.1 必做（1-2 个迭代）
1. 多轮编辑能力：支持“改第 3 个节点文本”“把这两步并行化”等 patch 指令。  
2. 可解释输出：返回“生成的 DSL + 渲染参数 + 校验结果”，便于人工修订。  
3. 质量门控升级：fail-open 改为可配置（strict/relaxed），并增加语法 lint + 渲染成功率校验。  
4. 模板系统：按场景提供流程图、时序图、架构图模板，降低首次失败率。  
5. 产物格式扩展：PNG + SVG + 可编辑源码（`.mmd`/`.html`）同时输出。

### 5.2 建议做（3-6 个月）
1. 多引擎路由：Mermaid/PlantUML/Graphviz/D2 自动选择或用户指定。  
2. 结构中间层（IR）：先把需求转成统一图模型，再编译到不同 DSL。  
3. 自动修复循环：语法报错/布局差 -> 反馈给 Agent 重写，直到通过阈值。  
4. 评测基准集：建立 100-300 条真实任务集，跟踪成功率、返工率、耗时、成本。  
5. 协作能力：版本对比、图变更 diff、审阅意见回写。

### 5.3 探索方向（6-12 个月）
1. 与文档平台深度集成（GitHub/GitLab/Notion/Confluence）。  
2. 从“图生成”升级为“图驱动知识库”，支持检索、复用和治理。  
3. 增加“从现有图片反向提取 DSL”能力，打通编辑闭环。

---

## 6. 建议聚焦领域
建议优先聚焦：**软件研发与技术运营文档（Docs-as-Code + Diagrams-as-Code）**。

原因：
- 需求强且高频，天然接受 Mermaid/PlantUML/Markdown 工作流。
- GitHub 等平台原生支持 Mermaid，易形成“生成 -> 提交 -> 审阅 -> 发布”闭环。
- 与你的现有技术栈匹配度最高，最易形成可复用模板和私有化部署优势。

不建议先做泛设计/海报方向：那是扩散模型主场，竞争维度不同。

---

## 7. 关键实验与里程碑（可直接执行）

### 7.1 30 天实验
1. 构建 50 条真实场景数据集（流程图/时序图/架构图）。  
2. 上线“源码 + 图片双输出”。  
3. 增加 strict 质量模式并统计通过率。

### 7.2 90 天目标
1. 多轮编辑上线（最小可用 patch 指令）。  
2. 引入第二渲染引擎（建议 PlantUML 或 Graphviz 二选一）。  
3. 发布质量看板：成功率、平均修复轮数、P95 生成时延、单图成本。

### 7.3 北极星指标（建议）
- `一次通过率`：无需人工重改即可接受的比例。  
- `可编辑回写率`：用户继续修改源码而不是重提需求的比例。  
- `平均生成总时延` 与 `单图总成本`。  
- `模板复用率`：复用模板生成的请求占比。

---

## 8. 风险与应对
- 风险：LLM 生成 DSL 语法错误。  
应对：语法检查 + 自动修复循环 + 最终回退模板。

- 风险：渲染安全（HTML/CSS/外链资源）。  
应对：严格沙箱、禁外链、白名单字体与资源、资源超时与大小限制。

- 风险：质量判断不稳定（VL 模型波动）。  
应对：多维规则校验优先，VL 仅做补充；strict 模式下不可直接 fail-open。

---

## 9. 参考来源（官方/一手）
- Mermaid 文档与 Mermaid Chart：  
  https://mermaid.js.org/  
  https://www.mermaidchart.com/  
- Mermaid CLI（渲染导出）：  
  https://github.com/mermaid-js/mermaid-cli  
- Playwright 截图能力：  
  https://playwright.dev/docs/screenshots  
- Graphviz 官方文档：  
  https://graphviz.org/doc/info/lang.html  
- PlantUML 官方站点：  
  https://plantuml.com/  
- D2 官方文档：  
  https://d2lang.com/  
- Kroki 官方文档：  
  https://docs.kroki.io/kroki/  
- Structurizr DSL（C4 建模）：  
  https://docs.structurizr.com/dsl  
- GitHub 对 Mermaid 的支持：  
  https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams  
- OpenAI Skills（与你当前安装技能相关）：  
  https://raw.githubusercontent.com/openai/skills/main/skills/.curated/playwright/SKILL.md  
  https://raw.githubusercontent.com/openai/skills/main/skills/.curated/screenshot/SKILL.md  
  https://raw.githubusercontent.com/openai/skills/main/skills/.curated/imagegen/SKILL.md
