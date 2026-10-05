# 各模块框架选型调查（Module Framework Selection Survey）

> 版本 v0.5 · 第五轮修订：§2.6 展开为"**LangChain 包架构拆解 + 逐模块不采用理由**"（含 v1 重组事实、灵活性缺口、按需单包边界与对导师口径）
> 版本 v0.4 · 第四轮修订：① 数据源定为 **OpenAlex 为主、arXiv 为辅**（NUS·英文文献·CS/软硬件/工科）；② 补存储引擎"选定 vs 主流"的**架构级优劣**（Kuzu vs Neo4j、Qdrant vs Milvus、SQLite 角色）；③ 补"为什么不选经典 LangChain"（分模块拆分后职责被单点组件承接）
> v0.3：每模块补业界主流对照（采用/未采用、优劣、规模化切换）；v0.2：成熟框架优先（导师意见）；v0.1 曾主推自研薄 harness，已废弃
> 适用范围：EE5003 硕士项目《智能多智能体文献研究助手（Context & Harness Engineering）》
> 输入约束：本机运行 · 每周自动运行 · 三界面（Topic / Report / Chat）· 论文关联+作者活跃度 · 自纠错（防漂移/防循环）· 评测内置 · 本地+云端双引擎（熔断/降级）· 云端用 DeepSeek(国产, OpenAI 兼容)
> 领域与语言（NUS）：**英文文献为主**，学科 = CS / 软硬件 / 工科（AI·ML、系统·软件、体系结构·硬件、网络·EDA 等）
> 数据源（v0.4 修订）：**OpenAlex 为主**（索引 IEEE/ACM 会议与期刊，含引用关系与 OA 定位）+ **arXiv 为辅**（追最新预印本）+ 自定义期刊/会议白名单（venue 过滤）

## 0. 选型决策原则与对比口径

**决策原则（贯穿全文）**
1. **主流框架优先（本人+导师一致取向）**：通用能力一律用生态好、社区大、可维护的主流框架；**框架可维护性 > 自研可控性**——后期工程复杂化时，框架的升级/文档/社区支持比自研代码更省心。
2. **自研最小化**：只保留两类自研——(a) 文献领域特有逻辑（漂移守卫、grounding 评测、折叠策略、事件模型）；(b) 主流框架确实不覆盖且不值得引重框架的薄胶水。**凡"不用某个主流框架"，本文件都给出明确理由与优劣对比。**
3. **单机可跑、本地优先**：能不引外部服务就不引；存储选嵌入式/本地模式。
4. **OpenAI 协议统一**：本地引擎与 DeepSeek 同协议 → 网关只需一套协议实现。
5. **可评测可回放**：每模块能埋点、留痕、导出数据（导师要求的"具体测试数据"）。
6. 主代码 Python 3.11+，前端 TS；先最小闭环再扩展（P1→P3→P4）。

**对比口径（每个模块固定回答 4 问）**
- Q1 当前选定是什么？ Q2 业界最常用的主流参照框架（1–2 个）是什么？
- Q3 若未采用该主流框架：为什么不选？两者优劣？ Q4 若后续工程化/规模化，能否切换到该主流框架？

**待定输入**
- 本地 GPU 显存未知 → 本地推理引擎可插拔（模块3）；部署形态：开发 Windows，周更服务器未知 → 组件跨平台。

---

## 1. 模块划分总览

| # | 模块 | 解决什么 | 对应分层 |
|---|---|---|---|
| 1 | 编排与多 Agent 框架 | 周更流水线编排、角色 agent、自纠错回路、断点续跑 | 编排层 + Harness |
| 2 | LLM 网关与路由 | 本地/云端统一调用、复杂度/敏感度路由、熔断降级、成本计量 | 模型层 |
| 3 | 本地推理引擎 | 本地跑 Llama/Qwen，OpenAI 兼容服务 | 模型层 |
| 4 | 关系图数据库 | 论文/作者关系、作者活跃度与方向演变查询 | 数据层 |
| 5 | 向量库与检索(RAG) | 语义召回、相关论文发现、novelty 辅助 | 数据层 |
| 6 | 元数据/全文解析与源适配 | 多源归一化、增量同步、PDF 解析、分块 | 采集层 |
| 7 | 调度与长任务运行 | 每周 cron、job 生命周期、看门狗、失败留痕 | Harness |
| 8 | Web 后端 | REST + SSE/WS、ORM、DB 迁移、事件总线 | 接口层 |
| 9 | Web 前端与可视化 | 三界面、过程回放、关系网络图 | 接口层 |
| 10 | 评测与可观测 | 幻觉/准确度/漂移指标、LLM-judge、轨迹回放 | 横切 |

---

## 2. 模块 1：编排与多 Agent 框架（核心决策）

### 2.1 职责与需求
- 周更流水线：`onboarding → scoping → planning → retrieval → map → analyze → report`，阶段可拆专职 agent。
- 对话场景的轻量 agent（多轮 + 工具调用）；显式控制流；长跑可中断/恢复；看门狗与自纠错（防漂移/循环，见 challenges-and-self-healing.md）；轨迹可回放。

### 2.2 可能遇到的问题
- 框架把控制流包办 → 自纠错变成"框架配置"；框架层太厚 → 排障与升级成本；自研过度 → 2–3k 行核心+测试反噬工期；自由对话式多 agent → 行为不可控。

### 2.3 候选对比

| 框架 | 定位 | 长跑/断点 | 确定性控制 | 多 agent | 结构化输出/工具 | streaming | 学习/调试成本 | DeepSeek/本地 | 适配 |
|---|---|---|---|---|---|---|---|---|---|
| **LangGraph**（LangChain 官方新一代） | 显式图状态机 | 内建 checkpointer(SQLite/PG)、时间旅行 | 最强：节点+条件边，控制流可见 | supervisor/react/子图 | with_structured_output | 完善 | 概念多、API 演进快→锁版本；生态最大 | base_url 即可 | ★★★★★ 主推 |
| AutoGen v0.4+（微软） | 对话式多 agent | 有状态管理 | 中 | 强(团队/群聊) | 支持但类型化弱 | 有 | 高、API 变动大 | 支持 | ★★★ |
| CrewAI | 角色+任务+流程 | 弱 | 弱–中 | 易用 | 支持 | 一般 | 低 | 支持 | ★★ |
| OpenAI Agents SDK | 轻量 agent+handoffs+guardrails | 会话内建，长跑自管 | 中 | 中 | 支持 | 内建 tracing | 低–中 | base_url 可用 | ★★★（对话页局部可选） |
| Pydantic AI | 类型安全 agent | 弱 | 中 | 弱–中 | 极强 | 一般 | 低–中 | 支持多家 | ★★★ |
| 国产(AgentScope/Qwen-Agent/MetaGPT) | 国内生态 | — | — | MetaGPT 团队式 | — | — | — | 兼容国产模型 | ★★ 补充对比 |
| DeepSeek Harness(TS) | 生产级 harness | 成熟 | 成熟 | 成熟 | — | 成熟 | 高(TS 栈) | 原生 | ★★★ 机制蓝本/对照，非底座 |

### 2.4 推荐：**LangGraph**
- 周更=显式状态图，**自纠错=条件边+节点内守卫**（看得见、可单测）；SQLite checkpointer 长跑恢复；事件流直通 Report/Chat；评测库同生态。
- 薄自研层（领域，量小）：工具集、守卫、折叠、评测指标、事件表。
- 贡献重定位：在 LangGraph 之上设计并量化 Context/Harness 工程模式（漂移自愈回路、grounding 评测、双引擎对比、折叠策略）——模式+数据是论文贡献，而非重造 agent 运行时。

### 2.5 主流框架对照
| 主流参照 | 生态/地位 | 是否采用 | 若未采用：关键理由 | 优劣摘要 | 规模化可切换？ |
|---|---|---|---|---|---|
| **LangGraph**（本模块主流） | LangChain 系第一大 agent 框架，生产级案例多 | ✅ 采用 | — | 图式确定性 + checkpoint + 流式俱全，与评测生态同源 | 本身就是规模化选项（官方 checkpoint 支持 PG，可水平拆分服务） |
| AutoGen / CrewAI（并列第二主流） | 微软系 / 社区热度高、上手快 | ❌ | AutoGen 偏"会话团队"，控制流不如显式图直观，长受控流水线难表达；CrewAI 编排黑盒化、确定性弱，长期自纠错难做 | AutoGen 强在自由协作研究；CrewAI 强在快速 demo。二者都不如 LangGraph 适合"显式状态机+守卫"需求 | 可（切换成本在编排层：把 node/edge 重写为对应抽象）；但无必要，LangGraph 已覆盖 |

### 2.6 为什么不直接用"经典 LangChain"（v0.5 展开：包架构 + 逐模块理由）

#### 2.6.1 LangChain 家族的真实架构（哪些是自研、哪些只是包装）

先纠正一个常见理解：**LangChain 不是"每个模块都自研引擎"的框架**，它本质是 **抽象层 + 集成包装层 + 少量自研实现**；真正的能力来自第三方库。并且 v1 做过一次大重组：旧版 chains / AgentExecutor / memory 迁至独立包 `langchain-classic`，编排交给 LangGraph（官方方向）。

| LangChain 组成 | 性质 | 底层真身 |
|---|---|---|
| `langchain-core` | **自研抽象层** | Runnable/LCEL、messages、tools、prompts、output parsers、callbacks、retrievers 基类 |
| `langchain`（v1） | **自研（薄）** | 基于 LangGraph 的 agent API（如 `create_agent`）+ middleware |
| `langchain-classic` | **自研（维护模式）** | 旧版 chains、AgentExecutor、memory —— v1 迁移后独立成包 |
| `langchain-community` | **包装集合** | pypdf、Unstructured、BeautifulSoup、rank_bm25… |
| `langchain-<provider>`（openai / anthropic / ollama…） | **包装** | 官方 SDK / HTTP API |
| `langchain-<vectorstore>`（qdrant / chroma…） | **包装** | 官方客户端（qdrant-client 等） |
| `langchain-text-splitters` | **自研（小）** | 递归/语义分块代码 |
| `langgraph`（+ `langgraph-checkpoint-*`） | **自研引擎** | 图状态机 + checkpoint + 流式 |
| `langserve` | **包装** | 把链暴露为 FastAPI 路由 |
| `langchain.evaluation` / **LangSmith** | 自研 hooks / **SaaS 平台** | 评测与追踪服务 |

**关键结论**：真正"自研"的是**编排（LangGraph）、旧链与记忆、分块、检索器、回调**；模型、向量库、解析、加载器这些**都是对第三方的薄包装**——"用 LangChain 的某个模块"往往等于"多一层包装去调用同一个第三方库"。

#### 2.6.2 逐模块对照：为什么不用它自带的模块

| 本项目模块 | 对应 LangChain 模块 | 采用 | 不采用理由（架构级） |
|---|---|---|---|
| 模块2 网关/路由 | `langchain-<provider>` 模型类 | ❌ | provider 差异被再抽象一层；加熔断/成本/敏感度策略要改链路代码；LiteLLM 更贴协议层，且 fallback/成本/多厂商由上游维护 |
| 模块5 向量库 | `langchain-<vectorstore>` | ❌ | 单向量库场景官方客户端更直接，且全功能（payload 过滤、本地模式、量化）不被包装层裁剪 |
| 模块6 文档加载 | `langchain-community` loaders | ❌ | 传递依赖重（Unstructured 等）；输出 `Document` 的元数据约定仍需二次归一化；本项目源固定 |
| 模块6 分块 | `langchain-text-splitters` | ❌（唯一可单包引入） | 分块须与本地 embedding/模型 token 预算严格对齐；自研约 50 行更可控 |
| 模块5/1 检索 | LangChain retrievers | ❌ | 检索过程被抽象隐藏；本项目要显式控制过滤、去重、novelty 判定、证据卡格式，评测要看到每一步 |
| 模块1 旧 Agent/记忆 | `langchain-classic` | ❌ | 长时状态、条件控制、断点恢复弱；官方已用 LangGraph 取代（v1 迁移即证据） |
| 模块1 编排 | **LangGraph** | ✅ **采用** | 家族里最新、最对口的一层；可脱离经典 LangChain 独立使用 |
| 模块10 评测 | `langchain.evaluation` / LangSmith | ❌ | LangSmith 为 SaaS（数据出境 + 付费）；漂移/自愈等领域指标必须自研；标准指标用 DeepEval |
| 模块8 服务化 | `langserve` | ❌ | 已自建 FastAPI + SSE + Job 注册表 + per-topic 锁；LangServe 不覆盖运行状态与三界面需求 |
| 横切 追踪 | callbacks | ❌（作真相源） | 事件表是回放/评测/审计的真相源，不能绑在框架回调抽象上 |

#### 2.6.3 "缺少灵活性"的五个具体点

1. **声明式组合 vs 条件控制流**：LCEL/链擅长"拼管道"，但难以自然表达"漂移→回退、失败→降级、超预算→中断"这类条件跳转；图式编排（LangGraph）才直观——这也是官方把编排迁到 LangGraph 的原因。
2. **隐藏的提示词与工具格式**：框架自带 prompt 模板与工具调用约定，模糊了"模型究竟看到什么"，影响可复现性与论文可控性。
3. **抽象泄漏**：异常类型、流式事件、重试行为都经过多层包装，排障要翻两层。
4. **版本耦合**：`langchain-core` 与各集成包版本矩阵强绑定；v1 大迁移把 chains 整体搬去 `langchain-classic`（旧代码 `import langchain.chains` 直接失败）→ 对一年制项目是实打实的维护风险。
5. **依赖过重**：loader/retriever 生态带入大量传递依赖，与"单机、轻依赖、零外部服务"的目标冲突。

#### 2.6.4 我们的采用边界

- **采用**：LangGraph（编排内核）+ 其依赖的 `langchain-core` 类型体系；评测用 DeepEval（独立于 LangChain）。
- **不采用**：经典 LangChain 全家桶（chains、AgentExecutor、memory、loaders、retrievers、模型类）。
- **按需单包引入**：将来若出现"语义分块""特殊格式加载""跨向量库"等真实需求，只安装对应的 `langchain-*` 单包，保持"分模块、轻依赖、可维护"。

#### 2.6.5 一句话口径（给导师/评审）

> 不用经典 LangChain，不是因为它是"自研框架"，而恰恰因为它大部分是**对第三方库的薄包装**：这些包装与本项目已选定的更专业组件（LiteLLM 网关、官方向量客户端、自研解析/分块）职责重合，还带来版本耦合、隐藏提示词与依赖负担；我们采用的是同一家族的新一代编排引擎 **LangGraph**——即"用家族里最新、最合适的一层"，其余能力按需单包引入。
>
> 参考：[LangChain v1 迁移指南](https://docs.langchain.com/oss/python/migrate/langchain-v1)（旧 chains/agents/memory 迁至 `langchain-classic`，编排以 LangGraph 为核心）。

---

## 3. 模块 2：LLM 网关与路由（含熔断/降级）

### 3.1 职责与需求
- 统一 chat/completion/embedding（本地引擎 ↔ DeepSeek 云），调用方不感知。
- 路由：复杂度 + 数据敏感度（保密强制本地）+ 可用性 + 成本；熔断/降级/重试退避；失败留痕。
- 计量：每次调用模型/时延/token/成本入事件表（local vs cloud 评测数据源）。

### 3.2 可能遇到的问题
- 各家 SDK 混用代码膨胀；网关进程成故障点/黑盒；敏感策略只在 prompt 层不可靠（须代码层强制）；成本/熔断无记录 → 评测无据。

### 3.3 候选对比

| 方案 | 优点 | 缺点/风险 | 适配 |
|---|---|---|---|
| **LiteLLM**（SDK Router 进程内 或 proxy） | 统一 100+ 家、内置 fallback/重试/负载均衡/成本与预算、活跃维护；OpenAI 兼容端点(DeepSeek/Ollama/vLLM)直接注册 | 抽象一层、需锁版本；敏感度等**业务路由仍在代码层**（薄） | ★★★★★ 主推 |
| 自研薄网关（~300 行） | 零依赖、全可控、与事件溯源天然一体 | 重试/熔断/成本/多厂商适配全要自己维护——**工程化后可维护性弱**，与本人"框架优先"取向冲突 | ★★★ 仅在"拒绝任何第三方抽象"时选 |
| OpenRouter | 免运维聚合 | 第三方中转、数据出境、不支持本地引擎 | ★★ |
| LangChain LCEL | 生态整合 | 抽象重、版本耦合、网关职责被稀释 | ★★ |

### 3.4 推荐：**LiteLLM（SDK Router 模式，进程内）**
- Router 注册 providers：`local-ollama / local-vllm / deepseek`（均 OpenAI 兼容）；利用其 fallback/重试/健康冷却做**熔断降级**第一层。
- 薄业务层（自研，~200 行）：① 敏感度路由函数（allow/deny 强制拦截，非 prompt 约束）；② 复杂度/成本路由（决定走哪个 deployment）；③ **自定义 callback** 把每次调用写入事件表（llm_call：时间/agent/route_reason/token/成本/时延）→ 评测与成本数据源。
- 规模化路径：SDK Router → 自托管 **proxy 模式**（多服务共享、统一密钥/预算/审计），无需改业务代码。

### 3.5 主流框架对照
| 主流参照 | 生态/地位 | 是否采用 | 若未采用：关键理由 | 优劣摘要 | 规模化可切换？ |
|---|---|---|---|---|---|
| **LiteLLM** | 自托管 LLM 网关事实标准（proxy 部署广） | ✅ 采用（SDK 起步） | — | 免维护 100+ 适配/重试/成本表；代价是一层抽象（锁版本+文档依赖） | ✅ SDK→proxy 平滑升级，正是规模化路径 |
| OpenRouter / one-api 类 | 云聚合（OpenRouter）/国内聚合网关 | ❌ | 第三方中转违背"本地优先+隐私"，且不代理本地引擎 | OpenRouter 省运维但数据出境；one-api 类国内多但社区与维护参差 | 一般不采用；除非多团队共享云 Key 治理 |

---

## 4. 模块 3：本地推理引擎

### 4.1 职责与需求
服务本地模型（Llama-3/Qwen2.5，7B–14B 视显存）为 OpenAI 兼容 /v1；周更批处理 + 对话低延迟 + local vs cloud 评测对照；显存未知→档位可配置；开发机 Windows。

### 4.2 可能遇到的问题
- vLLM 在 Windows 原生不可用（需 WSL2/Linux）；显存不足 OOM；并发排队无超时；模型文件管理。

### 4.3 候选对比

| 方案 | 优点 | 缺点/风险 | 适配 |
|---|---|---|---|
| **Ollama** | Windows/Linux 原生、即装即用、GGUF 量化省显存、模型管理简单 | 高并发吞吐弱于 vLLM | ★★★★★ 开发默认 |
| **vLLM** | 吞吐/批处理业界主流，生产首选，OpenAI 兼容完善 | Linux only、显存占用高、配置多 | ★★★★★ 生产(Linux)档 |
| llama.cpp server | 极轻、CPU 可跑 | 功能较原始 | ★★★★ 无 GPU 兜底 |
| SGLang | 同档位、RadixAttention 利于多轮 | 生态略小 | ★★★ |
| LM Studio 等 | 桌面友好 | 不适合程序化服务 | ★★ |

### 4.4 推荐
**Ollama（开发默认）+ vLLM（Linux 生产档）+ llama.cpp（兜底）**，引擎/模型/量化写入配置；"显存预算→KV 估算→折叠/降级/切云"联动放 Context 层，与引擎解耦。

### 4.5 主流框架对照
| 主流参照 | 生态/地位 | 是否采用 | 若未采用：关键理由 | 优劣摘要 | 规模化可切换？ |
|---|---|---|---|---|---|
| **vLLM** | 本地/私有化 LLM 服务事实标准（吞吐、连续批处理） | ✅ 采用（生产档） | — | 吞吐/批处理最强；原生 Linux | ✅ 本身就是规模化方案（多卡/分布式已支持） |
| SGLang（次主流） | 新兴、性能口碑好 | ❌ | 生态/文档略小，团队更熟 vLLM；功能重叠 | 各有胜负（Radix 前缀复用 vs 生态成熟） | 可（同为 OpenAI 兼容，切换只影响部署层） |

---

## 5. 模块 4：关系图数据库（论文关联/作者活跃度——导师强调点）

### 5.1 职责与需求
节点 Paper/Author/Venue/Topic；边 AUTHORED/CITES/CO_AUTHOR/BELONGS_TO/SIMILAR_TO（均带时间）；作者动向（近 N 年发文、合作者演变、方向位移）；增量 MERGE；规模万级 → 单机。

### 5.2 可能遇到的问题
- 无查询语言/内存图 → 分析难写、规模崩（NetworkX）；服务型图库 JVM 重 + 许可证；作者同名消歧（预留不做）；时间不建模则"动向"不可答。

### 5.3 候选对比

| 方案 | 优点 | 缺点/风险 | 适配 |
|---|---|---|---|
| **Kuzu（嵌入式）** | pip 零服务、Cypher 子集、列式、导入快、Python 友好 | 较年轻、工具少、单写者（本场景无碍） | ★★★★★ |
| Neo4j Community | 图生态事实标准：Cypher 全、工具/资料最多 | JVM 常驻重、Community 为 GPLv3、部署复杂 | ★★★★（规模升级备选） |
| Memgraph | Cypher 兼容、快 | 内存型需服务 | ★★★ |
| NebulaGraph | 国产、分布式、性能强 | 分布式部署重、学习曲线 | ★★★ |
| NetworkX | 零依赖原型 | 无持久化/查询语言 | ★★ |

### 5.4 推荐：**Kuzu（嵌入式）**
与"单机 Python 全栈、零外部服务"一致；元数据级规模绰绰有余。落地：author 带 name_norm+合并预留；边带时间；topic 为子图视图、作者跨 topic 共享；**查询先按标准 Cypher 风格写**（控制与 Neo4j 方言差异）以便迁移。

### 5.5 主流框架对照
| 主流参照 | 生态/地位 | 是否采用 | 若未采用：关键理由 | 优劣摘要 | 规模化可切换？ |
|---|---|---|---|---|---|
| **Neo4j Community** | 图数据库事实标准（生态/工具/资料第一） | ❌（现阶段） | 本系统单机+万级节点：Neo4j 的 JVM 常驻/部署/GPLv3 对个人项目过重；Kuzu 零运维已满足全部查询 | Neo4j：生态成熟、功能全、可视化工具多；Kuzu：嵌入式免运维、快、轻——功能缺口在"规模/高级算法/多人协作"时出现 | ✅ 可（图服务抽象隔离，schema/查询按标准 Cypher 写即可平移）；届时也可选 NebulaGraph（更大规模） |
| NebulaGraph（国产次主流） | 国内分布式图库 | ❌ | 分布式部署/运维重，单机场景杀鸡用牛刀 | 面向超大规模 | ✅ 多机海量时才考虑 |

**架构差异要点（为什么现阶段不选最主流的 Neo4j，v0.4 补）**：Kuzu = **进程内嵌入式**（Python 链接 C++ 核心，打开目录即用，零网络往返），**列式存储 + 向量化执行**（节点/关系表按列存放，扫描聚合快），MIT 许可、pip 即用；Neo4j = **独立 JVM 服务进程**（客户端经 Bolt/HTTP 网络协议访问），完整 Cypher + APOC/GDS 图算法与 Bloom 等生态，但 Community 为 **GPLv3**、需常驻内存与部署运维。差距只在"规模到百万级+/多用户并发写/要图算法库/要可视化全家桶"时才值得换——届时经图服务接口平移即可（schema 与查询已按标准 Cypher 风格写）。

---

## 6. 模块 5：向量库与检索 / 嵌入（RAG）

### 6.1 职责与需求
摘要/片段 embedding 存储；元数据过滤（source/date/topic/paper_id）；检索 agent 与 Chat 的 RAG、novelty 辅助；增量 upsert 幂等；本地优先；万级向量；嵌入本地 bge-m3（多语言 1024d）。

### 6.2 可能遇到的问题
- 纯向量无过滤 → 退化语义硬搜；无持久化 → 每周重建不可持续；纯稠密对精确术语召回差 → 需混合检索；嵌入与生成模型抢显存。

### 6.3 候选对比

| 方案 | 优点 | 缺点/风险 | 适配 |
|---|---|---|---|
| **Qdrant（本地 embedded 起步）** | 过滤/量化/混合检索完善；可平滑升 server；生态好 | 本地模式单进程，目录备份自管 | ★★★★★ |
| LanceDB | 零配置、全文+向量混合、Arrow 友好 | 生态较新、复杂功能少 | ★★★★ |
| Chroma | 最易上手 | 过滤弱、性能/稳定口碑一般 | ★★★ |
| Milvus | 功能全、分布式 | 部署重（etcd/MinIO 等）、单机过度 | ★★ |
| FAISS | 检索标杆 | 无过滤/元数据/持久化，全自造 | ★★ |
| pgvector | PG 生态顺带 | 需先迁 PG；向量功能弱于专用库 | ★★★ |

### 6.4 推荐：**Qdrant（本地 embedded 起步）**
collection 全库共享，topic 过滤用 payload 字段；novelty = 检索命中但图中无此 paper_id；嵌入默认 bge-m3（CPU 可跑），经模块2 网关统一调用。

### 6.5 主流框架对照
| 主流参照 | 生态/地位 | 是否采用 | 若未采用：关键理由 | 优劣摘要 | 规模化可切换？ |
|---|---|---|---|---|---|
| **Qdrant** | 自托管向量库主流（与 Milvus、Chroma 并列头部） | ✅ 采用 | — | 过滤/混合检索完善 + 单机 local 模式 + server 平滑升级 | ✅ local→server→集群 同一产品线 |
| Milvus（并列主流，分布式向） | 分布式向量库标杆（尤其大规模/云原生） | ❌ | 需 etcd/MinIO/多组件，单机万级严重过度 | Milvus 强在亿级/高可用；Qdrant 强在轻量+渐进 | ✅ 数据达千万级或需高可用时迁移（接口层隔离） |

**架构差异要点（为什么现阶段不选 Milvus，v0.4 补）**：Qdrant = **Rust 单引擎**，三种形态同一产品线：embedded（引擎直接跑在 Python 进程内，本项目用）→ 单机 server → 分布式集群，本地模式把"向量库"降为进程内依赖、零外部组件；Milvus = **云原生存算分离**（proxy/coordinator/querynode 等多组件 + etcd 元数据 + 对象存储/消息队列），分布式与亿级优势在单机万级场景是负资产。检索服务接口已隔离，数据规模/高可用需求到来时再迁 Milvus（或 Qdrant 集群）。

---

## 7. 模块 6：元数据/全文解析与源适配

### 7.1 职责与需求
- **数据源策略（v0.4 修订）**：**OpenAlex 为主**——CS/软硬件/工科文献主体（会议+期刊，含 IEEE Xplore / ACM DL 收录论文）都在其索引中，且提供引用关系（`referenced_works`）与 OA 全文定位；**arXiv 为辅**——追最新预印本（category 白名单）；**自定义源** = 期刊/会议白名单（OpenAlex `source.id` 过滤）∪ arXiv category（例：NeurIPS/ICML/ICLR/CVPR/ACL/OSDI/SOSP/ASPLOS/ISCA/MICRO/HPCA/SIGCOMM/ICSE/FSE/DAC/ICCAD 及 IEEE 期刊…，数据驱动）。
- IEEE/ACM **无开放抓取 API**：不直连，全部经 OpenAlex 取元数据与引用。
- 语言：**英文文献为主**（NUS·CS/软硬件/工科）→ 检索、报告默认英文。
- 归一化：各源 → 统一 `Paper`（canonical id）；增量同步 + 指纹去重；OA 全文 PDF→文本→分块；非 OA（付费墙）仅摘要入库；解析健壮（fallback、可重跑、留痕）。

### 7.2 可能遇到的问题
- 多源 schema 差异；限流封禁；PDF 质量差；源字段变动崩管道。
- IEEE/ACM 大量论文**非 OA（付费墙）** → 仅摘要可用，全文检索与 grounding 覆盖受限（评测口径需注明）。
- 硬件/EDA 文献常只发期刊、**不进 arXiv** → 若只用 arXiv 会系统性漏检——这正是"OpenAlex 为主"的原因。

### 7.3 候选对比

| 子项 | 候选 | 结论 |
|---|---|---|
| OpenAlex 客户端 | pyalex vs 原生 httpx | **pyalex**（内置筛选/分页/邮件头） |
| arXiv 客户端 | arxiv 库 vs Atom 手写 | **arxiv 库** |
| PDF 文本 | PyMuPDF 主 + pdfplumber 兜底 vs GROBID vs Unstructured/Docling | **PyMuPDF+pdfplumber**（轻）；GROBID 等见 7.5 |
| 分块 | LangChain splitter vs 自研递归分块 | **自研**（递归字符+token 预算，对齐 embedding/上下文档） |
| 全文存储 | 文件系统+SQLite 索引 vs DB blob | 文件系统+索引 |

### 7.4 推荐
**OpenAlex 主 + arXiv 辅**，轻依赖组合：`httpx + pyalex + arxiv + PyMuPDF(+pdfplumber 兜底)`；Pydantic 定义统一 `Paper`；自定义源 = venue/category 白名单数据驱动，无新代码路径。

**是否自研（分层，v0.4 补）**：抓取协议 / PDF 抽取 / OCR / embedding 全部用现成 API 与库；**自研 = 领域胶水**——SourceAdapter 统一接口、字段映射、canonical id（DOI → OpenAlex W → arxiv，加前缀防冲突）与作者键（name_norm + 源内 id）、增量游标（sync_state）与幂等 upsert、分块策略（递归 + token 预算）。解析管道做成**可重跑、失败留痕**的 queue（配合模块7 调度），即 Harness Engineering 的"文档解析运行时"落点。

### 7.5 主流框架对照

| 主流参照 | 生态/地位 | 是否采用 | 若未采用：关键理由 | 优劣摘要 | 规模化可切换？ |
|---|---|---|---|---|---|
| **Unstructured** | 文档解析/EChR 预处理主流库 | ❌（现阶段） | 依赖重、主要价值在多样非结构化源与"分块进 RAG 向量库"编排；本项目源固定（arXiv/OpenAlex+OA PDF），PyMuPDF 已够且可控 | Unstructured：覆盖面广、省事；PyMuPDF：轻、快、可控——缺口在"复杂版式/表格/扫描件"时出现 | ✅ 需要深度版面/表格/多格式时引入（接口：统一"抽取器"抽象） |
| **Docling**(IBM) / GROBID（次主流，学术向） | Docling 现代文档理解；GROBID 参考文献解析标准 | ❌ | GROBID 只在"全文引用图"升级时有用；Docling 同 Unstructured 理由 | Docling：版面+结构理解强；GROBID：引用解析业界标准 | ✅ 全文引用抽取/图表理解升级时采用（对应关系深度二期） |

---

## 8. 模块 7：调度与长任务运行管理

### 8.1 职责与需求
每周每 topic cron + 手动触发；job 状态机（queued/running/failed/…）可取消；看门狗（时间上限/阶段超时/停滞/循环）；事件实时推 Web + 落库；进程重启恢复。

### 8.2 可能遇到的问题
- 裸 cron 无状态无留痕；Celery/Redis 单机过重；长跑与 Web 同进程互相拖累；周更与手动运行重叠需 per-topic 锁。

### 8.3 候选对比

| 方案 | 优点 | 缺点/风险 | 适配 |
|---|---|---|---|
| **APScheduler（触发器）+ DB-backed Job 记录层** | 进程内 cron；job 状态/锁/事件自持且与 Web 同源；单机够用 | 分布式不支持 | ★★★★★ |
| Celery + beat + Redis | 任务队列生态成熟 | broker 运维重、周更低频用不上 | ★★ |
| Prefect / Dagster | 重试/调度/UI 完善 | 全家桶重、与 LangGraph 编排语义重叠 | ★★ |
| Temporal（durable execution） | 工业级长任务/重试/心跳 | 需要服务端集群、概念重 | ★★（规模化再看） |

### 8.4 推荐
**APScheduler 管"何时触发" + LangGraph 管"怎么跑" + 薄 Job 记录层管"状态/锁/事件落库"**（Job 层是簿记而非执行内核，量小）。同一 topic 串行锁；进程重启扫描 interrupted 供手动重跑。

### 8.5 主流框架对照
| 主流参照 | 生态/地位 | 是否采用 | 若未采用：关键理由 | 优劣摘要 | 规模化可切换？ |
|---|---|---|---|---|---|
| **Celery**（Python 任务队列事实标准） | 分布式任务队列主流 | ❌（现阶段） | 需 Redis broker/worker，单机+周更低频用不上；"执行编排"已由 LangGraph 承担，Celery 与之语义重叠 | Celery 强在横向扩容/通用任务；APScheduler 强在进程内零运维——缺的是"多机/多 worker"时才有价值 | ✅ 多机/高并发/微服务化时把 run 提交改为 Celery 任务即可 |
| Prefect / Dagster / Temporal（工作流/durable 次主流） | 数据/工作流工程主流；Temporal 为 agent 长任务新宠 | ❌ | 与 LangGraph 图编排功能重叠且更重；单机不划算 | 强在调度/重试/可视化全家桶与持久执行 | ✅ 若项目演化为"多租户 SaaS 化长任务平台"，Temporal 值得重估 |

---

## 9. 模块 8：Web 后端（API / ORM / 实时推送）

### 9.1 职责与需求
Topic/Report/Chat REST；SSE 实时事件、Chat 流式；ORM+迁移（交付物含 DB 迁移）；SQLite(WAL) 起步可迁 PG；阻塞工作异步化。

### 9.2 可能遇到的问题
- Django 同步模型对 SSE/长任务实时推送别扭；SQLite 并发写；事件先广播后落库会丢；schema 前后端漂移。

### 9.3 候选对比

| 方案 | 优点 | 缺点/风险 | 适配 |
|---|---|---|---|
| **FastAPI** | asyncio、SSE/WS 顺手、Pydantic v2 双用于 API 与 agent 协议、OpenAPI 自动文档、主流 | 无内置后台任务（由模块7/1 补） | ★★★★★ |
| Django + DRF + Channels | 全家桶、Admin | 同步模型+async 缝合成本、样板重 | ★★★ |
| Flask | 轻 | SSE/校验/文档自搭 | ★★★ |
| NestJS(Node) | 若全栈 TS | 与 Python 主栈割裂 | ★★ |

### 9.4 推荐
FastAPI + SQLAlchemy 2.0(async, typed) + Alembic；SSE 为主、双向操作再补 WS；Pydantic 单源（agent 协议=API schema=DB typed）；SQLite→PG 连接串可切。

### 9.5 主流框架对照
| 主流参照 | 生态/地位 | 是否采用 | 若未采用：关键理由 | 优劣摘要 | 规模化可切换？ |
|---|---|---|---|---|---|
| **FastAPI** | Python Web API 主流（async 向事实标准） | ✅ 采用 | — | 与 Pydantic/agent 层类型同源，实时推送天然 | ✅ uvicorn 多 worker + PG 即规模化的标准路径 |
| Django REST（次主流，企业向） | 全家桶、后台管理成熟 | ❌ | 同步 ORM 与 SSE/长连接缝合成本高；本项目无复杂后台管理需求 | Django 强在 Admin/生态全；FastAPI 强在 async/类型/轻——本项目三类页面交互都是实时型 | 可（但需重写 async 层，不建议） |

---

## 10. 模块 9：Web 前端与可视化

### 10.1 职责与需求
三界面：Topic 管理 / Report（过程时间线回放 + 每周报告历史 + 关系网络图与作者视图）/ Chat；后端 REST/SSE 契约隔离，前端可独立更换。

### 10.2 可能遇到的问题
- 关系图库选错卡顿（万级需 topic 子图裁剪）；回放成大列表不可读（需分类过滤）；SSE+多页状态管理失控；前后端 schema 漂移。

### 10.3 候选对比（框架 + 图可视化两层）

| 层 | 候选 | 结论 |
|---|---|---|
| 框架 | React 18+TS vs Vue 3+TS | 两者均主流；推荐 **Vue3+TS+Vite**（或 React，随组内熟悉度，被 API 隔离） |
| UI 组件 | Element Plus(Vue) / Ant Design(React) | 随框架 |
| 数据获取 | TanStack Query / Pinia+axios；SSE=EventSource | 随框架 |
| 关系图 | ECharts graph / AntV G6 / Cytoscape.js | **ECharts 起步**；复杂交互/大图 → AntV G6 |
| 时间线回放 | 自研轻组件 | 无需重型库 |
| API 类型 | openapi-typescript | 随 FastAPI |

### 10.4 推荐
Vue3|React + TS + Vite + Element Plus/AntD + ECharts；SSE 实时；作者节点详情面板（近 N 年发文/合作者/方向演变）数据来自模块4 图服务。

### 10.5 主流框架对照
| 主流参照 | 生态/地位 | 是否采用 | 若未采用：关键理由 | 优劣摘要 | 规模化可切换？ |
|---|---|---|---|---|---|
| **React**（全球第一大前端生态） | 生态/岗位/组件库最大 | ⭕ 二选一（看组内熟悉度） | 与 Vue 等价可选；两者都被后端 API 契约隔离 | React：生态最全（AntD/MUI/shadcn）；Vue3：上手快、中文社区好、单文件组件 | ✅ 前端层随时可切，不影响后端 |
| Next.js（React 全栈向主流） | 全栈框架 | ❌ | 后端已是 FastAPI，再上 Node 全栈重复且分裂 | Next 强在 SSR/一体化部署；本项目是本地 SPA+Python 后端 | 不需要 |
| 图可视化：AntV G6 / Cytoscape.js（图分析主流） | 复杂网络图 | ⭕ 预留 | ECharts 够起步；G6/Cytoscape 在"大规模/自定义交互/布局算法"时更强 | — | ✅ 关系图变复杂（千人千面布局/圈选/聚类）时替换视图层组件 |

---

## 11. 模块 10：评测与可观测（导师要求设计期内置；详见 evaluation-plan.md）

### 11.1 职责与需求
周报忠实度/准确率、对话准确率与召回、自愈有效性（漂移检出/恢复率）、local vs cloud 对比；grounding 客观优先 + LLM-judge + 人工抽查；运行即埋点、全量留痕回放。

### 11.2 可能遇到的问题
- 评测后补 → 埋点缺失（红线：P1 起埋点）；judge 无 rubric 主观漂移；漂移"无标准答案"需代理指标；轨迹不可回放。

### 11.3 候选对比

| 方案 | 优点 | 缺点/风险 | 适配 |
|---|---|---|---|
| **DeepEval** | LLM-judge/指标库（faithfulness/groundedness…）、pytest 风格回归、可自定义 metric、活跃 | 抽象需适配论文级口径；版本迭代快（锁版本） | ★★★★★ 评测外壳主采用 |
| ragas | RAG 指标研究化 | 偏 RAG 流水线，agent/漂移场景弱 | ★★★ 参考口径 |
| promptfoo | 用例文件化回归/红队/对比 | 偏固定用例批测 | ★★★ 可选补充 |
| LangSmith | 追踪+评测云端一体 | 数据出境、付费、绑定 LangChain 系 | ★★ |
| LangFuse | OSS LLM 可观测（self-host） | 需 Postgres(+Redis) 等组件，与单机零服务冲突 | ★★（规模化/多服务再上） |
| OpenTelemetry | 标准可观测协议 | 运维型，论文级事件模型仍自建 | ★★ 后续补 |
| 自研领域模块 | 领域指标（漂移/自愈/guard 事件）+ 事件存储回放 | 只做框架不覆盖的部分 | ★★★★★（必要，量小） |

### 11.4 推荐
**采用 DeepEval 做评测外壳**（LLM-judge、faithfulness/groundedness 等标准指标、pytest 式回归），**自研只保留领域模块**：guard 事件/漂移自愈指标、fault-injector（自愈可测的前提）、事件表回放与指标聚合导出。judge 异源、rubric 固定、人工抽查校准（报告 κ）。

### 11.5 主流框架对照
| 主流参照 | 生态/地位 | 是否采用 | 若未采用：关键理由 | 优劣摘要 | 规模化可切换？ |
|---|---|---|---|---|---|
| **DeepEval** | OSS LLM 评测主流之一 | ✅ 采用（外壳） | — | 开箱 metric/judge + 自定义扩展；与自研领域模块互补 | ✅ 评测即代码，规模化为测试集/CI 集成 |
| LangSmith / LangFuse（可观测主流） | SaaS/自托管 LLM 追踪 | ❌（现阶段） | LangSmith 数据出境+付费；LangFuse 需 PG/Redis，破坏单机零服务原则 | 强在通用 trace/反馈闭环；弱在领域事件(guard/phase)模型 | ✅ 多服务/多用户/上线运维时引入 LangFuse 或 OTel（事件表仍为真相源） |

---

## 12. 推荐技术栈总览与主流采用结论

| 模块 | 采用（默认） | 未采用的主流（理由一句话） | 规模化切换路径 |
|---|---|---|---|
| 1 编排/多 Agent | **LangGraph** | AutoGen/CrewAI（控制流/确定性不如显式图） | 无需切（本身规模化） |
| 2 LLM 网关 | **LiteLLM SDK** + 薄业务路由/计量 | OpenRouter（数据出境） | SDK→proxy |
| 3 本地推理 | **Ollama(dev) + vLLM(prod)** + llama.cpp 兜底 | SGLang（生态略小） | vLLM 已可多卡/分布式 |
| 4 关系图 | **Kuzu(嵌入式)** | Neo4j Community（JVM/GPL/部署重，规模未到） | 图服务抽象 → Neo4j/NebulaGraph |
| 5 向量库 | **Qdrant 本地模式** | Milvus（分布式组件重，规模未到） | local→server→集群 |
| 6 解析/源适配 | pyalex+arxiv+PyMuPDF(+pdfplumber) | Unstructured/Docling/GROBID（依赖重，范围未到） | 需要全文引用/复杂版面时引入 |
| 7 调度/长任务 | APScheduler + LangGraph + 薄 Job 记录 | Celery/Prefect/Temporal（单机不需要；与 LangGraph 重叠） | 多机/多租户 → Celery 或 Temporal |
| 8 Web 后端 | **FastAPI + SQLAlchemy + Alembic + SSE** | Django（同步模型不适合实时推送） | uvicorn 多 worker + PG |
| 9 Web 前端 | **Vue3 或 React + TS + Vite + ECharts** | Next.js（后端已是 FastAPI）；G6/Cytoscape 视复杂度 | 视图层随时可换 |
| 10 评测/可观测 | **DeepEval 外壳 + 自研领域评测/事件回放** | LangSmith/LangFuse（出境/需 PG，现阶段过重） | 上线运维 → LangFuse/OTel |

**全栈依赖画像**：langgraph(+checkpoint-sqlite), litellm, fastapi, uvicorn, sqlalchemy, alembic, pydantic, apscheduler, httpx, pyalex, arxiv, pymupdf, qdrant-client, kuzu, ollama 客户端/vLLM(部署), deepeval；前端 vue|react + vite + element-plus|antd + echarts + openapi-typescript。无 Redis/无消息队列/无外部服务依赖（部署机可选容器化）。

### 12.1 存储三引擎并存与分工（v0.4 补：为什么关系/图/向量三个库同时用）
同一批实体（论文/作者/topic）按"查询类型"投影为三种组织形态，每引擎只答自己擅长的问题；**关系型 SQLite 是运行层核心**（不是可选项）。

| 引擎 | 组织形态 | 负责查询示例 | 不擅长 |
|---|---|---|---|
| SQLite（关系型，运行核心） | 行式表 + 事务（SQLAlchemy 2.0 + Alembic） | topic/run/事件/报告/对话/计量——流水账与审计**真相源** | 多跳关系、模糊语义 |
| Kuzu（图） | 节点 + 带时间边（Cypher） | "作者近 3 年发文 / 合作者变化 / 引用链" | 模糊内容匹配 |
| Qdrant（向量） | embedding + payload 过滤 | "与这段描述语义最接近的论文" | 任何结构关系 |

- 写入一次（采集管道），投影三份（写放大在万级规模可接受）；以 paper_id 全局稳定键互引；事件表（SQLite）是回放/评测/审计的共同真相源。
- 切换路径均已隔离：SQLite→PostgreSQL（连接串/Alembic）、Kuzu→Neo4j/NebulaGraph（图服务接口）、Qdrant local→server→集群（同一产品线）。

---

## 13. 组合兼容性与关键风险

**组合自洽性**
- OpenAI 协议贯通：LiteLLM ← Ollama/vLLM/DeepSeek；路由/熔断/计量单一实现。
- 事件模型贯通：LangGraph 节点 → Job 层 → SSE → Report 页（同一事件表=真相源）。
- Pydantic 单源：agent 协议 = API schema = DB typed 层。
- Kuzu(关系) + Qdrant(向量) + SQLite(运行/事件) 分工无重叠，稳定键互引。

**关键风险与对策**
| 风险 | 对策 |
|---|---|
| GPU 显存未知 | 模块3 引擎可插拔；显存→KV 预算联动在 Context 层 |
| 框架 API 演进（LangGraph/LiteLLM/DeepEval） | 锁版本；按官方稳定模式写；框架相关代码收敛在少数文件（图定义/网关配置/评测配置） |
| 框架 checkpoint 与自库状态重复 | LangGraph checkpointer 只管运行内恢复；SQLite 管领域数据+事件+指标 |
| LiteLLM 抽象黑盒 | 关键字段自定义 callback 校验；锁版本 + 官方文档 |
| 作者同名/异名 | 不做消歧，schema 预留合并键；评测注明口径 |
| 源 API 限流/字段变动 | 礼貌限速+重试；Pydantic 校验告警不崩管道 |
| SQLite 并发写 | WAL + 单写者封装；预留 PG |
| LLM 非确定性影响评测 | 记录 sampling；judge 异源；固定配置复现 |
| 数据出境（隐私） | 敏感度强制拦截在 LiteLLM 上层代码 |

---

## 14. 需要导师/组会确认的选型决策点

1. 编排内核 **LangGraph**（不用经典 LangChain 的理由见 §2.6）+ 网关 **LiteLLM** 的组合是否认可（主流取向：能框架则框架）；
2. 评测采用 **DeepEval 外壳 + 自研领域模块** 的拆分是否认可（自研仅 guard/漂移/grounding 领域指标）；
3. 数据源范围：**OpenAlex 主 / arXiv 辅** + 期刊/会议白名单（CS·软硬件·工科、英文文献）与报告默认英文是否认可；
4. 部署机形态与 GPU（定模块3 本地档主档）；
5. 前端 React 或 Vue；
6. 是否需要"与 DeepSeek Harness 对照章节"；
7. 测试 topic 集（3–5 个，英文、可核验事实密集）与评测周数。

## 15. 参考来源（部分）

- LangGraph vs AutoGen vs CrewAI 对比（[Latenode](https://latenode.com/blog/langgraph-vs-autogen-vs-crewai) / [LLM-Agents-Ecosystem-Handbook](https://github.com/oxbshw/LLM-Agents-Ecosystem-Handbook/blob/main/docs/framework_comparison.md)）；框架横向盘点（[mcp.directory](https://mcp.directory/blog/langgraph-vs-crewai-vs-letta-vs-autogen-2026) / [腾讯云开发者：8 大 AI Agent 框架](https://developer.cloud.tencent.cn/article/2545052?policyId=1003)）
- LangGraph 持久化/checkpoint（[官方文档](https://mintlify.wiki/langchain-ai/langgraph/guides/persistence)）；Pydantic AI vs LangGraph（[ZenML](https://www.zenml.io/blog/pydantic-ai-vs-langgraph)）
- 本地推理引擎对比（[TensorFoundry](https://tensorfoundry.io/blog/llm-inference-servers-compared)）；Neo4j vs Kuzu vs Memgraph（[Till Freitag](https://till-freitag.com/blog/neo4j-kuzu-memgraph-vergleich)）
- OpenRouter vs LiteLLM（[OpenRouter Blog](https://openrouter.ai/blog/insights/openrouter-vs-litellm) / [LiteLLM Routing](https://github.com/BerriAI/litellm/blob/44c99241/docs/my-website/docs/routing.md)）
- LLM 评测框架盘点（[futureagi](https://futureagi.com/blog/best-open-source-eval-frameworks-2026/) / [AI & Agents: Eval Tools 2025](https://fast.io/resources/best-tools-ai-agent-evaluation/)）

> 注：框架生态变动快，文中特性描述以撰写时公开资料为准；各模块 PoC 时以最新版本文档复核。
> 配套：组会速览《framework-selection-brief.md》与《architecture-overview.md》需按 v0.3 同步（模块2 网关 LiteLLM、模块10 DeepEval）。
