# 硕士项目初步架构分析：多智能体文献研究助手（Context & Harness Engineering）

> 状态：v0.2 已并入组会 #2 需求要点（导师：先做各模块框架选型与对比）。依据：项目 Abstract + 组会记录 + 我的工程判断 + DeepSeek Harness 对照。

## 0. 一句话定位

这不是一个"检索工具"或"prompt 包装"，本质是一个**面向长期任务（long-horizon）、确定性可审计的多智能体自治系统**。学术价值不在"用 LLM 读文献"，而在用 **Context Engineering + Harness Engineering** 把不受控的模型输出，约束成受控、可复现、可溯源的系统行为。本工作区运行于 DeepSeek Harness（DSH）之上——它是该范式的生产级实例，可同时充当参考实现、实验基座与论文 evidence。

## 1. 六个目标的工程转译

| 项目目标 | 工程含义 | 子系统 |
|---|---|---|
| 1 双引擎后端 | 模型网关 + 路由策略（按任务复杂度 / 数据敏感度分流 local vs cloud） | LLM gateway、provider adapters、本地推理服务 |
| 2 多智能体编排 | Orchestrator + 专职 agent（Retrieval / Network Mapping / Update Cron）+ 任务/结果协议 | agent team、任务路由 |
| 3 Context Engineering | 上下文预算管理：sliding window、摘要折叠、按引用注入、token 计量 | context manager |
| 4 Harness Engineering | 状态机、评估回路、重试、文档解析运行时、沙箱、看门狗 | harness core |
| 5 持续时间跟踪 | 增量抓取 → 指纹去重 → 向量库+图库更新 → novelty 标记 | tracker + DB |
| 6 通用 CLI | 交互多轮问答、topic onboarding、后台监控、报告 | CLI / jobs |

## 2. 建议分层架构

```
接口层 L6 : CLI（交互多轮 / 命令模式）
编排层 L5 : Orchestrator（计划→分派→回收→评价→迭代）+ agent 消息协议
Harness L4: 每 track 状态机 · eval/retry 回路 · 沙箱 · 看门狗(轮次/token/停滞) · 溯源日志
Context L3: 上下文预算 · 滑动窗口/折叠 · 窗外记忆(spill) · 检索片段注入
模型层  L2 : 模型网关 + 路由策略（复杂度+敏感度）→ local(Llama/Qwen) | cloud(GPT/Claude)
数据层  L1 : 文档库(raw/parsed) · 向量库 · 图库 · 事件/状态存储(provenance)
采集层  L0 : 源适配器(arXiv/OpenAlex/…) · 增量同步 · 解析管道(PDF→text→OCR fallback)
横切: 配置 · 遥测/日志 · 敏感度策略 · 评测埋点
```

要点：**确定性来自状态机，自由度只给 agent 轮次内部**。

## 3. 核心机制设计草案

### 3.1 研究主题生命周期状态机（确定性骨架）
每 track 一条状态机 + 事件日志（event-sourced），控制流不进 prompt：

```
onboarding → scoping(关键词/种子文献/边界)
           → planning(子任务分解)
           → retrieval(增量) → ingest+parse(去重/指纹)
           → map(向量/图更新, novelty 标记) → synthesize(周报/问答)
           → monitoring(周期回 retrieval)
```
- 状态迁移仅由 harness 触发；agent 只产出"动作 + 结构化结果"，不能自跳状态。
- 全部状态与中间产物落库 → 长跑可暂停/重启/审计/回放。

### 3.2 双引擎路由与隐私边界
- 两级路由：(a) 能力路由——任务复杂度阈值；(b) 敏感度路由——数据分级策略配置，命中保密标记强制 local 或脱敏后才可出网。
- 默认零信任线：全文与用户标注 confidential 语料不出本机；公开元数据/摘要可按策略送云。
- Local 侧 vLLM/Ollama/llama.cpp + embedding 模型（如 bge-m3）**共享显存** → 上下文长度、KV cache、embedding 批量需统一计量（见 3.3）。

### 3.3 Context Engineering（论文重点之一）
原则：**窗口是稀缺资源按预算管理；记忆在窗外，引用进窗内**。
- 每 agent 会话一个 token 预算（token-meter 记账）。
- 长文档不进窗口：解析分块入向量库，窗口只放"检索片段 + 溯源引用"。
- 折叠策略：sliding window + 分层压缩（旧对话/旧任务结果 → 结构化摘要/状态快照，需时反查）。
- 注入点固定 schema：system(track 状态) / user(当前任务) / tool-result pool，杜绝随手粘贴全文。
- 本地显存预算折算：context budget → KV cache 估算，超出即折叠或降级路由。

### 3.4 Harness：评估回路与自纠错
不靠"模型自觉"，靠**外部可判定检查 + 有界重试**：
- 结构化输出 JSON-schema 强校验，不合法即重试/降级。
- 事实性检查：citation 必须回查存在于语料库；指纹去重。
- 模型级 groundedness/faithfulness 打分（可选），低于阈值重生成或转人工。
- 重试状态机：max_attempts、退避、降级链 cloud→local→大→小→人工。
- 看门狗：轮次上限、token/时间预算、停滞检测。
- 文档解析管道每级 fallback（pdfplumber→PyMuPDF→OCR），失败不进库可重跑。
- 全程事件溯源：谁/何时/何模型/何工具/何产出 → 可回放（thesis 素材 + eval 数据源）。

### 3.5 持续时间跟踪
- 向量库（语义召回：abstract/snippet embedding）+ 图库（paper-concept-author-venue-citation，网络演化）。
- 增量同步：只拉 since-last（arXiv/OpenAlex 更新时间戳），入库前 sha 指纹去重。
- novelty 规则：候选文献与既有 track"相关但图中无此节点/边" → 新论文 → notify。
- 时间维度显式建模（收录/发现/源 updated 时间），支持"比同行早发现"类统计。

### 3.6 CLI
- 交互多轮问答（回答带 citation 溯源）；命令：`research onboard <topic>` / `watch` / `status` / `report <track>`。
- 长任务转后台 job：可查进度/取消/恢复。

## 4. 关键选型草案（待组会后定）

| 组件 | 候选 | 倾向 | 理由 |
|---|---|---|---|
| 语言/框架 | Python；自研薄 harness vs LangGraph | 自研薄核心 | thesis 卖点是 harness engineering；框架现成则创新点变薄。可先 PoC 对比再定 |
| 网关 | LiteLLM / 自研 adapter | LiteLLM 起步 | 一条 API 覆盖 openai/anthropic/ollama/vllm |
| 本地推理 | Ollama / llama.cpp / vLLM | 看 GPU 定 | 显存决定模型档位与 batch |
| 向量库 | Qdrant / LanceDB / Chroma | LanceDB / Qdrant 本地 | 免服务、够用；评测记录维度 |
| 图库 | Neo4j / kuzu / networkx | Neo4j 社区版 或 kuzu | 规模不大可轻量；Neo4j 生态成熟 |
| 状态/事件 | SQLite + WAL | SQLite | 单机、可迁移、可审计 |
| 数据源 | arXiv / OpenAlex / Crossref / Semantic Scholar | OpenAlex + arXiv | 覆盖广、免费、时间戳规范 |

## 5. 待确认问题（等组会细节收敛）

1. 硬件：本地 GPU 型号/显存 → 决定 local 模型档位与显存预算设计。
2. 数据源范围：仅 arXiv/单领域还是多学科 → 影响解析与评测设计。
3. "确定性执行"验收口径：是否要求"同输入→同状态轨迹"的可复现实验。
4. 评测数据集形态：导师是否已有期待（tracking 准确率 / 端到端时延 / 幻觉率，local vs cloud 对比维度）。
5. 发布与知识产权：是否开源、论文目标、是否设 DSH 对比章节。
6. 时间线：组会频率、中期/最终节点 → 决定路线图切法。

## 6. 一年路线图草案

- P0 (2–4w)：需求与数据源冻结；本地模型 + 一个云 API 跑通。
- P1 (6–8w)：网关+路由、CLI 骨架、onboarding；**单 agent 最小闭环**（先立状态机与解析管道，验证 harness 基础）。
- P2 (8w)：Harness 核心：eval/retry/看门狗/上下文折叠；确定性复现测试。
- P3 (6–8w)：多 agent 化：三个专职 agent + orchestrator + 溯源日志。
- P4 (6w)：时间跟踪：DB schema、增量同步、novelty、周报。
- P5 (6–8w)：评测数据集 + local vs cloud 对照实验（P2 起并行埋点）。
- P6 (4–6w)：Context/Harness 配置规范文档 + 论文。
交付物映射：仓库←P1–P4；规范文档←P2–P3；eval 数据集←P5；论文←全程。

## 7. 现成参考：DeepSeek Harness（本工作区运行环境）

| 你的机制 | DSH 子系统（源码/文档） | 可学什么 |
|---|---|---|
| 模型网关 | packages/llm、api、credentials；docs/cookbook/adding-an-llm-adapter.md | provider adapter 设计 |
| 多 agent | packages/subagent、workflow；docs/subsystems/{subagent,workflow,agent-team}.md | 后台子代理生命周期、fan-out/阶段编排、schema 强校验 |
| 长期/定时任务 | packages/goal、jobs、schedule、todo | goal 轮次/revision、job kill/output 生命周期、cron |
| Harness/护栏 | packages/sandbox、guard、plan；docs/subsystems/* | 权限分档与升级、计划模式、防御边界 |
| Context eng. | packages/context、compaction、spill；token-meter 文档 | 会话折叠、窗外记忆、token 记账 |
| 可靠性文化 | docs/postmortem/*.md（0001–0004…） | 失败复盘文档化；错误处理分类法可入 thesis |
| 评测 | docs/testing.md、packages/{invariants,feedback} | 模型可见行为级测试与不变量 |

注：映射依据包名与本会话中实际使用的工具行为；深入前可逐一精读对应文档再引用。
额外机会：eval 的 local vs cloud 对照，可复用 DSH 风格 runner 做 provider 对照实验。

## 8. 下一步

发上次组会细节（导师反馈、范围、deadline）后：
(a) 更新本分析；(b) 产出下一级文档，建议顺序：① 状态机与 agent 消息协议规范 → ② 数据库 schema（向量+图+事件）→ ③ Context budget / sliding-window 设计。也可指定优先深入某块。

## 附：组会记录

### 组会 #2（日期 ____）——导师布置：先做架构与各模块框架选型对比

- 当前任务：各模块用什么框架、做框架对比分析 → 后续产出《整体架构 md》与《各模块选型调查 md》。
- 系统需求（导师口径）：
  - **每周定期运行**：agent 依选定 topic 自动检索网上最新论文 → 一次长时自动运行 → 生成该 topic 的报告。topic 由用户增删改。
  - **论文关联（强调）**：整理论文时做多论文之间的关系建模，依据作者活跃度等，使用户可查看某作者近期的动向与研究方向的演变。
  - **自我修正机制（强调）**：长时间自动运行需防"方向错误 / 死循环 / 偏离 topic"。
  - **多 agent**：需考虑多 agent 协作场景。
  - **界面至少三个**：① topic 选择界面（增删改）；② 每 topic 的 report 界面（展示每周自动调查过程——工具调用、思考情况——与每次最终报告）；③ 每 topic 的对话界面（用户描述问题/需求，agent 依据 report / 网络信息 / RAG 解答）。
  - **性能量化（提醒，需在设计期内置）**：幻觉率、回答准确度、每周自动运行防偏离的效果等 → 需要具体测试数据结果。
- 待澄清问题与答案（需求澄清 Q&A，已确认）：
  - 代码形态：**未定** → 选型文档需对比「自研薄 harness vs 成熟编排框架（LangGraph/CrewAI 等）vs 以 DSH 为底座」并给出建议。
  - 引擎切换（导师原要求）：本地模型与云 API **智能切换**，须含**熔断（circuit breaker）、降级（fallback）**等机制；无固定 GPU 规格 → 本地档位做成可配置。
  - 云 API：**DeepSeek / 国产 API** 可用（OpenAI 兼容协议）→ 云端默认 DeepSeek；本地 Ollama/vLLM 亦 OpenAI 兼容，网关可统一 OpenAI 协议层。
  - 数据源：**arXiv + OpenAlex + 自定义源**（指定期刊/会议列表）。
  - 关系网络：**元数据级起步**（引用/共著/主题相近），schema 预留全文级扩展。
  - UI：**本地 Web，FastAPI + React/Vue 前后端分离**。
  - 每周运行：**全自动无人值守**；自纠错 + 失败留痕 + 手动重跑。
  - 评测：**混合方案**（citation-grounding 客观检查 + LLM-judge + 人工抽查）。

### 关联项目（导师的另一项目：Jetson 本地多模态 LLM）——导师提过可能与本项目对接

- 目标：在 NVIDIA Jetson Xavier NX（8/16GB 共享显存、Volta 架构）上部署**完全离线**的开源多模态 LLM。
- 六目标：模型选型（轻量 VLM 基准评测）· 量化/剪枝（面向 Volta）· CLI 多轮对话 · OpenAI 兼容异步 API 网关（供本地 agent）· 零信任沙箱（数据不出设备）· 资源仪表盘（两接口间算力权衡 + 遥测 + token 授权日志）。
- 与本项目潜在对接面：① Jetson 的 OpenAI 兼容网关 = 本系统 §3"本地推理引擎"的真实后端路径（协议已一致）；② 多模态（vision）→ 扫描 PDF/图表/公式的文档解析增强；③ 仪表盘遥测 → Context 预算与路由决策输入（显存/排队/吞吐）；④ 零信任沙箱 ↔ 敏感度路由强制策略，隐私叙事统一；⑤ token 授权日志 ↔ llm_call 计量，可对齐做跨项目核算与评测；⑥ 评测协同：本系统的 grounding/幻觉评测可作为其压缩质量的第三方评测；其本地引擎可作"local vs cloud"对照的第三个引擎（Jetson-local / PC-local / DeepSeek-cloud）。
- 硬件现实（影响本地档预期）：Xavier NX 为 Volta 架构，TensorRT-LLM 官方主要面向 Orin+，llama.cpp/CUDA 路线更现实；本地模型档位预计 ≤2–4B 级量化 VLM/小 LLM，长上下文与高吞吐受限 → 路由默认"隐私敏感才走本地"，长任务/高质量走云，周更批量需排队协调。
- 状态：仅背景了解，对接深度与接口契约待澄清（见对话）。
