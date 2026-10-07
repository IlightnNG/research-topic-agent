# 整体架构设计（Architecture Overview）

> 版本 v0.2 · 与《project/framework-selection.md v0.2》配套（编排内核 = LangGraph，成熟框架优先）
> 状态：结构定稿，待导师确认项见 §9；Jetson 关联项目仅作背景备注（见 §8），未纳入正式架构

## 1. 设计目标与约束（速览）

| 维度 | 结论（来源） |
|---|---|
| 系统定位 | 每周自动运行 + 随时对话的文献研究多 agent 系统；Topic 为一级实体 |
| 编排内核 | **LangGraph**（周更=显式状态图；对话=react agent）；薄自研层=领域工具/守卫/评测/折叠 |
| 模型通道 | 自研薄网关：本地（Ollama 默认 / vLLM 备选）+ 云端 DeepSeek；OpenAI 协议统一；熔断/降级/计量 |
| 存储 | SQLite（运行/报告/事件/指标）+ Kuzu（论文/作者/关系图）+ Qdrant 本地（向量/RAG） |
| 数据源 | arXiv + OpenAlex + 自定义源（期刊/会议白名单）；增量同步 + 指纹去重 |
| 界面 | 本地 Web（FastAPI + SSE；Vue3/React + TS + ECharts）；三页面：Topic / Report / Chat |
| 运行模式 | 每周自动、全自动无人值守；自纠错 + 失败留痕 + 手动重跑 |
| 评测 | 设计期内置：citation-grounding + LLM-judge + 人工抽查；local vs cloud 对照 |
| 主语言 | Python 3.11+（前端 TS）；单机可跑、免外部服务（无 Redis/DB broker） |

---

## 2. 总体分层架构

```
┌────────────────────────────────────────────────────────────────────┐
│ 接口层 L6   Web（Vue3/React + ECharts）：Topic 页 / Report 页 / Chat 页│
│             FastAPI：REST + SSE（运行事件推送、Chat 流式）            │
├────────────────────────────────────────────────────────────────────┤
│ 应用层 L5   Topic 服务 · Run/Job 服务 · Chat 服务 · Graph 服务(作者视图) │
│             评测服务(指标/报告)                                      │
├────────────────────────────────────────────────────────────────────┤
│ 编排层 L4   LangGraph：周更流水线图(节点+条件边) · 对话 react agent   │
│             薄自研：漂移/循环守卫 · 看门狗 · 事件 sink · 重试策略      │
├────────────────────────────────────────────────────────────────────┤
│ Context L3  token 预算 · 折叠/摘要节点 · 检索注入槽 · KV 估算联动路由   │
├────────────────────────────────────────────────────────────────────┤
│ 模型层 L2   自研 LLM 网关：providers{local(Ollama/vLLM), cloud(DeepSeek)}│
│             路由(复杂度/敏感度) · 熔断/降级 · llm_call 计量            │
├────────────────────────────────────────────────────────────────────┤
│ 领域服务 L1 检索代理工具 · 图/向量读写 · 报告生成 · 解析管道(元数据/PDF) │
├────────────────────────────────────────────────────────────────────┤
│ 数据层 L0   SQLite(WAL) · Kuzu(嵌入式) · Qdrant(本地) · 文件(全文缓存)  │
│ 采集 L0'   源适配器(arXiv/OpenAlex/白名单) · 增量同步 · APScheduler     │
└────────────────────────────────────────────────────────────────────┘
横切：事件溯源(真相源) · 配置 · 遥测/计量 · 安全(敏感度强制策略) · 评测埋点
```

**框架/自研分工一句话**：LangGraph 提供"图执行 + checkpoint + streaming"；自研提供"文献领域可靠性"——守卫、评测、折叠、事件表、网关路由。两者职责不重叠。

---

## 3. 核心运行时设计

### 3.1 Topic 生命周期状态机（域层，跨周持久）
```
[new] → scoping(关键词/种子文献/scope_statement/边界)
      → active(进入周更循环)
         └─ 每周期：run_state: queued → running → succeeded | failed(留痕,可手动重跑)
      → paused(用户停用) ↔ active
      → archived
```
- 每 topic 持有：scope_statement（漂移检测基准）、订阅源白名单、调度配置、图子图视图。
- 同一 topic 同时只允许一个 run（串行锁）；不同 topic 可错峰并发。

### 3.2 单次周更运行 = 一张 LangGraph 显式状态图
节点（node，可为角色 agent 或确定性处理）：
```
scoping → planning → retrieval_agent → ingest_parse(确定性)
        → map_update(图/向量, 确定性) → novelty_check → analyze_agent
        → report_agent → quality_guard → [成功] finalize(存报告+指标)
```
条件边（自纠错入口，见 3.3）：
- `scope_guard` 失败 → 回 `planning`（带 feedback，≤N 次）
- `retrieval` 空/异常 → 重试 → 降级（换源/换模型）→ 跳 ingest 用存量
- `quality_guard` 不达标 → 回 `analyze/report`（≤N 次）
- 任何节点超时/看门狗触发 → 终止并 annotate（不阻塞下周）
- checkpoint：LangGraph checkpointer(SQLite) 提供断点/恢复；进程重启后 queued/running 的 run 可续跑或标记 interrupted

**角色 agent 划分**（LangGraph 内作为节点或子图，均受同一状态机约束）：
| Agent | 职责 | 主要工具 |
|---|---|---|
| retrieval_agent | 增量检索、相关度筛选、去重 | 源适配器、Qdrant 检索、指纹 |
| map_update / novelty | 关系写入、作者聚合、新论文标记（确定性为主） | Kuzu、Qdrant |
| analyze_agent | 主题分析、作者动向解读、趋势归纳 | Kuzu 查询、RAG |
| report_agent | 生成周报（结构化大纲→成文） | 模板 + LLM |
| quality_guard | 检查/评审（见 3.3） | 守卫工具 + LLM-judge |
| chat_agent | 对话页问答（独立小图） | 检索、Kuzu、读周报 |

### 3.3 自纠错 / 防漂移 / 防循环（导师强调点，落地为"守卫 + 条件边"）
| 故障 | 检测器（节点前后执行，写 guard_trigger 事件） | 处置（条件边） |
|---|---|---|
| **主题漂移** | 对 agent 阶段性产出（检索 query/摘要/报告片段）做 embedding，与 scope_statement 余弦 < 阈值；或检索结果中 out-of-scope 占比过高 | 回 planning 重新 scoping，带 feedback；超限 → 终止 + annotate |
| **方向错误** | 阶段产物缺失/违反 schema；引用无法回查 | 重试一次 → 换 provider → 回上一状态 |
| **死循环** | 最近 k 个工具调用签名哈希出现重复环；或状态无进展（新增信息量≈0） | 强制 replan（清局部子状态）→ 仍重复 → 终止留痕 |
| **停滞/超时** | 单节点超时；整 run 时间预算；LangGraph recursion_limit | 重试→降级→终止留痕 |
| **质量不达标** | grounding/连贯性 judge 分 < 阈值 | 回 analyze/report 重写（≤N 次）→ 附人工复查标记 |

升级阶梯（全局一致）：`retry(2) → degrade(换 provider/模型档) → replan → abort+annotate`；每一步都写事件，供 Report 页与评测统计"自恢复成功率"。

### 3.4 对话流程（Chat 页）
- 入口判定：问题涉及"某周报/某 topic/某作者"→ 工具型 react agent（LangGraph 小图）；否则通用问答同图。
- 工具集：`search_papers`（Qdrant+源）、`query_graph`（Kuzu：作者动向/共著/引用）、`read_report`（周报历史）、`web_search`（可选）。
- 每次回答强制附来源（paper_id / report_id），前端可点开溯源；不可回查的声明标为"推测"。
- 敏感度策略同样生效（涉密输入不出本地 providers）。

### 3.5 双引擎路由与熔断降级（网关策略表，优先级从高到低）
| 优先级 | 条件 | 动作 |
|---|---|---|
| 1 | 数据敏感度=sensitive | provider 强制 ∈ {local}（其余 deny） |
| 2 | 本地 provider 健康 & 任务属"简单档"（短问答/抽取/格式化） | local（成本≈0） |
| 3 | 本地过载/排队>阈值 或 任务复杂（长报告/长推理/大上下文） | cloud(DeepSeek) |
| 4 | cloud 故障（熔断 OPEN/半开失败达阈值） | 降级 local（若质量档可接受）或排队重试 |
| 5 | 全部失败 | 失败留痕 → 终止该步并 annotate（不静默） |

- 熔断器状态（closed/open/half-open）按 provider 独立维护；重试退避 + jitter；路由决策写 `llm_call.route_reason`。
- 计量：每次调用落 `llm_calls`（provider/model/token/时延/成本/route_reason）→ 评测与成本看板数据源。

### 3.6 Context Engineering 落地（预算/折叠/注入）
- 每个 agent 调用前按状态计算 token 预算（state 摘要 + 工具结果池），超预算先折叠：
  1. 检索历史/旧工具结果 → 摘要节点（结构化要点 + 引用）；
  2. 长对话（chat）→ 滑动窗口 + 摘要记忆；
  3. 长文档永不整篇进窗：解析分块进 Qdrant，窗内只放检索片段 + 溯源引用。
- 注入槽固定：`system(scope_statement + 状态 + 政策)` / `user(当前步指令)` / `tools(带引用的结果卡片)`。
- 显存/成本联动：估算 KV 开销（context tokens × provider 档位），超出本地档容量 → 折叠或路由云（§3.5 第 3 条）。
- LangGraph state 本身即"跨步记忆"：只保留结构化摘要 + 指针，避免 state 无限膨胀。

### 3.7 事件溯源与回放（真相源）
事件表统一记录：`phase_change / tool_call / llm_call / guard_trigger / message / error / metric`。
- Report 页"过程回放" = 按 run_id 读事件时间线（过滤分类展示）；
- 评测 = 事件聚合；审计/复现 = 事件回放（结合固定 sampling 参数）；
- 日志与事件的边界、字段字典与"日志 ↔ 事件 ↔ 上下文快照"三向关联规范见 `implementation/logging-and-observability.md`（日志可轮转，事件不可变）。

---

## 4. 数据设计

### 4.1 三存储分工
| 存储 | 内容 | 为何不合并 |
|---|---|---|
| SQLite(WAL) | topics、runs、run_events、reports、chat、llm_calls、metrics、sync_state、eval 结果 | 关系型操作/事务/迁移（Alembic），事件真相源 |
| Kuzu（嵌入式图） | Paper/Author/Venue 节点与关系（引用/共著/隶属/相似），时间字段 | 图查询（作者动向/网络）专用 |
| Qdrant(本地) | 论文摘要/片段 embedding，payload 过滤 | 语义召回 + 元数据过滤 |
| 文件系统 | 原始/解析后全文（按 paper_id 目录） | 避免 DB 膨胀，PDF 重解析 |

键策略：paper_id（canonical，如 openalex id / arxiv id 归一）为全局稳定键，三存储同键互引；author_id 预留合并机制（同名消歧：**二期低优先级，延后而非取消**）。

### 4.2 SQLite schema 草案（表清单）
- `topics(id, name, description, scope_statement, status, config_json, schedule_cron, created_at, updated_at)`
- `runs(id, topic_id, trigger[weekly|manual], state, error, started_at, finished_at, config_snapshot_json)`
- `run_events(id, run_id, ts, type, node, agent, payload_json)` 索引(run_id,ts)
- `reports(id, topic_id, run_id, period, title, content_md, metrics_snapshot_json, created_at)`
- `chat_sessions(id, topic_id, created_at)`；`chat_messages(id, session_id, role, content, citations_json, run_id_ref, ts)`
- `llm_calls(id, ts, run_id, agent, provider, model, route_reason, req_tokens, resp_tokens, latency_ms, cost)` 
- `metrics(id, scope[run|topic|eval], scope_id, metric, value, meta_json, ts)` 
- `sync_state(source, last_cursor, last_success_at, status, error)`
- `eval_judgments(id, target_type[report|chat], target_id, metric, score, judge_model, human, ts)`

### 4.3 图模型（Kuzu）
- 节点：`Paper{paper_id,title,abstract,venue,year,published_at,discovered_at,updated_at,source,doi}`；`Author{author_id,name_norm}`；`Venue{venue_id,name}`；`Topic{topic_id,name,scope_statement}`
- 边：`PAPER_AUTHOR(p,a,year)` · `CITES(p→p)` · `PUBLISHED_IN(p→v)` · `BELONGS_TO(p→topic, added_at)` · `SIMILAR_TO(p→p, score, computed_at)`（由向量相似度定期写）
- 代表查询（作者动向）：某 author 近 N 年发文时间线（按 year 聚合）；合作者集合逐年差异（CO_AUTHOR 派生）；论文关键词/embedding 质心逐年位移（方向演变）。
- 实测修正（S1/S1b，2026-10-07）：白名单记录 `referenced_works` 完整率仅 1.5–14.3%（宽召回 25–27%，且 DOI 交叉核对确认非版本问题）→ **`CITES` 边以 `cited_by` 反向构边为主**（用"引用方的 references"补出被引关系），Crossref 补源列为待评估；`Paper` 节点增加 `merged_ids`（去重合并的多版本 id）与 `citers_checked_at`（反向抓取水位）。
- topic 为图上子图视图；作者节点跨 topic 共享（跨领域动向可查）。

### 4.4 向量（Qdrant）
- collection `papers`：向量 = bge-m3(1024d，本地) 对摘要（后续加全文分块 collection `chunks`）；payload = `{paper_id, title, source, year, published_at, discovered_at, topic_ids[]}`。
- 检索 = 向量 + payload 过滤（date/source/topic）；novelty 候选 = 检索命中但 Kuzu 中无 BELONGS_TO/无此 paper_id。

---

## 5. 接口与数据流

### 5.1 每周自动运行时序
```
APScheduler 触发(topic_i, cron) → 创建 run(queued) → 广播事件
 → 运行器激活 LangGraph 图：scoping→…→finalize
     · 每节点进出/工具调用/LLM 调用/守卫触发 → 事件写 SQLite + 推 SSE
     · 断点：checkpoint(SQLite)；异常：重试/降级/终止留痕（§3.3）
 → 成功后写 reports + metrics；事件流结束；Report 页可回放全过程
```

### 5.2 对话时序
```
用户消息 → POST /api/topics/{id}/chat → chat_agent 工具循环
 → 回答与 citations → SSE 流式返回 + 落 chat_messages
```

### 5.3 API 草案
- `GET/POST/PATCH/DELETE /api/topics`；`POST /api/topics/{id}/run`（手动触发）；`GET /api/topics/{id}/runs`
- `GET /api/runs/{id}/events`；`GET /api/runs/{id}/stream`（SSE 实时）
- `GET /api/topics/{id}/reports`；`GET/POST /api/topics/{id}/chat`（SSE）
- `GET /api/graph/authors/{id}`；`GET /api/graph/topics/{id}/network`
- `GET /api/metrics/summary`；`GET /api/sources`（同步状态/手动同步）

---

## 6. 三界面规格映射

| 页面 | 内容 | 数据来源 |
|---|---|---|
| Topic 页 | 列表/新建/编辑/删除/启停；调度与源白名单配置；"立即运行" | topics API |
| Report 页 | ① 运行过程回放时间线（按 phase/tool/thinking/guard 过滤，实时 SSE）② 每周报告历史（markdown + 指标快照）③ 论文/作者关系网络图（topic 子图，点作者看动向卡片） | runs/events/reports/graph API |
| Chat 页 | 多轮对话，答案带 citation 链接；可追问作者/周报/相关论文 | chat API(SSE) + graph |

## 7. 评测与量化设计（导师要求：设计期内置）

| 指标 | 计算方式 | 埋点位置 |
|---|---|---|
| 回答/报告准确度 | citation-grounding：陈述能否在引用的论文摘要/全文回查；LLM-judge 打分；人工抽查校准 | report 生成后、chat 每次回答 |
| 幻觉率 | 无法 grounding 的陈述占比（抽样评估集） | eval 服务读 events+reports |
| 防漂移/自纠错有效性 | 每 run 统计：guard_trigger 数、自恢复次数、abort 数、恢复成功率 | guard 事件聚合 |
| 循环/停滞 | 重复工具签名环触发次数 | 同上 |
| local vs cloud | 同一任务集（生成用两档模型）的准确度/时延/token/成本 | llm_calls + eval 结果 |
| 检索质量（辅助） | 命中率/相关度人工抽检（周报引用一致性） | retrieval 事件 |

- 协议：固定测试 topic 集（3–5 个）连续 ≥4 周周更；全部事件入 metrics 表；导出脚本生成论文图表。
- judge 与生成异源（如生成 local/DeepSeek，judge 用另一家）减少自偏好；rubric 固定 + 小样本人工一致性报告。
- 可复现：生成 sampling 参数随事件记录；eval 与复现均固定配置。

## 8. 部署形态与配置
- 单进程 uvicorn(FastAPI) 承载 Web + 调度器 + 运行器（asyncio）；CPU 密集（PDF 解析/embedding 批量）走线程池或独立 worker（预留）。
- 目录：`config.yaml`；`data/{app.db, kuzu/, qdrant/, papers/}`；前端构建产物静态托管。
- 配置面：providers（本地档位/云 key）、路由策略、守卫阈值、调度 cron、评测开关。
- 无外部服务依赖；Windows 开发机直跑，Linux 部署可选容器化。
- 备注（非正式路径）：本地推理后端未来可能多一个"Jetson 本地服务"档位（导师另一项目，设备/进度未定，见 project/project-analysis.md"关联项目"，届时仅需在网关 provider 注册表中加一条）。

## 9. 待导师/组会确认项（承接选型文档 §14）
1. 编排内核 LangGraph 认可度（备选 AutoGen / OpenAI Agents SDK）；贡献重定位口径（§2.5 选型文档）
2. 部署机/GPU 形态（本地引擎主档）
3. 前端 React or Vue
4. 测试 topic 集与评测周数
5. 是否设 DSH / Jetson 对照章节（评测维度是否加第三引擎）

## 10. 演进路线与里程碑验收
| 阶段 | 目标 | 验收 |
|---|---|---|
| P1 最小闭环(≈6–8w) | 单 topic 手动触发跑通：检索→入库→报告；FastAPI+SSE+Report 页雏形；llm_call 埋点 | 一次 run 全流程事件可回放 |
| P2 Harness(≈8w) | LangGraph 流水线图 + 守卫/看门狗 + checkpoint；网关熔断；确定性单测（录制 LLM 交互夹具） | 注入故障（超时/漂移）能自动恢复并留痕 |
| P3 多 agent + 上下文(≈6–8w) | 角色拆分、折叠策略、Chat 页上线 | 对话带 citation；折叠后质量不劣化（评测） |
| P4 周更与图(≈6w) | APScheduler 周更、novelty、作者动向查询、Report 页网络图 | 连续 2 周无人值守自动出报 |
| P5 评测(≈6–8w，与 P2–P4 并行) | 测试 topic 集跑 ≥4 周，local vs cloud 数据收集、judge 校准 | 指标表 + 论文图表 |
| P6 文档(≈4–6w) | Context/Harness 配置规范 + 论文 | 交付物齐套 |

## 关联文档
- 选型与理由：《project/framework-selection.md》（v0.2）
- 需求与会议记录：《project/project-analysis.md》（含关联项目备注）
