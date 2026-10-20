# Phase 1.1 —— 收口规范、模块完成判据与修复步骤

> **文档性质**：**规范性文件（冻结契约）**。它是 Phase 1 收口的唯一判据来源。
> 与 `phase1-implementation-steps.md`（建设计划）的关系：那份回答"怎么建"，这份回答"**什么算建完**、以及**到此为止不再修什么**"。
>
> **版本**：1.1.1 ｜ **生效条件**：经你 review 后冻结。冻结后任何改动必须升版本号并在 §8 记录，禁止口头变更。
> **基线**：`pytest 230 passed`、`ruff clean`、`check_structure 129/129`、真实数据 100 篇 arXiv 端到端通过。
> **冻结记录**：2026-10-19 经项目负责人确认冻结；F6（前端规范化）顺延至 Phase 1.2，技术栈定为 **Vue 3**。

---

## 0. 这份文档要解决的问题

过去的问题是"**完成**"没有判据，导致每次检查都发现新的"待完善"，修复无边界。本文件用三条机制终止这种循环：

1. **范围冻结**：Phase 1.1 只允许做 §6 的 F1–F10 十步；任何新想法进 §5 backlog，**不得插入当前批次**。
2. **判据可执行**：每个模块的"完成"= 指定命令返回指定结果。**没有可执行判据的条目，不算目标**（只能算 backlog）。
3. **缺陷分级**：只有 P0 在 Phase 1.1 修；P1 选做；P2 一律延后到 Phase 2。**"未实现"不是缺陷**，是 backlog。

> **判定原则（关键）**：本文件的"完成"是**范围完成**，不是"完美"。凡列入 §5 Out-of-Scope 的条目，**即使未做也不阻塞 Phase 1.1 结束**——因为"不做"是明确决策，不是遗漏。

---

## 1. 三条硬规则

| 规则 | 内容 | 违反的后果 |
|---|---|---|
| **R1 范围冻结** | 只做 F1–F10；新需求进 §5 | 范围蔓延，判据失效 |
| **R2 红项优先** | 每步先跑基线，只修 P0 红项；不"顺手优化" | 引入回归，检查面再度膨胀 |
| **R3 单步可逆** | 每步结束必须：全量 `pytest` 绿 + 该步验收命令通过 + 文档更新；否则回滚该步 | 不可回退，无法定位责任 |

---

## 2. 全局完成判据（Phase 1.1 Done）

Phase 1.1 **结束**当且仅当以下 6 条同时成立：

| # | 判据 | 验证命令 | 期望 |
|---|---|---|---|
| G1 | 全量测试绿 | `uv run pytest -q` | `230+ passed`，0 failed |
| G2 | 静态检查干净 | `uv run ruff check .` | `All checks passed!` |
| G3 | 结构与 schema 一致 | `uv run python scripts/check_structure.py`；`lit-agent db status` | `129/129`；schema `1.0`、24 表 |
| G4 | 离线全链路 | `uv run python scripts/verify_phase1.py --offline` | 10/10 断言 PASS |
| G5 | 真实数据全链路 | `uv run python scripts/verify_phase1.py --online` | 10/10 PASS（含幂等与三库对账） |
| G6 | 文档三件套定稿 | 见 §7 文档 | RESULTS 定稿 / ADR-0006 存在 / known-gaps 存在 |

> **反向定义（重要，已确认接受）**：只要 G1–G6 全绿且 §5 中所有 P0 关闭，**Phase 1.1 即为完成**。此后发现的任何新问题，一律按 §4 分级进入 backlog，**不重新打开 Phase 1.1**。

---

## 3. 模块级目标、完成判据、重难点

图例：**DoD** = 可执行判据；**OOS** = 本阶段明确不做。

### 3.1 基座（config / logging / errors / structure / doctor）

| 项 | 内容 |
|---|---|
| **本阶段目标** | 配置可加载、路径集中在 D 盘、错误码可查、结构自检可信、doctor 能诊断 |
| **DoD** | ① `lit-agent doctor` → 6/6 OK；② `check_structure` → 129/129；③ 错误码表含 `E_SRC_AUTH` 且 `action_for()` 有映射；④ 配置缺字段时报 `E_CONFIG_INVALID` 而非 KeyError |
| **重难点** | 非 ASCII 路径（禁 editable install）、`.ps1`/`ini` 必须 ASCII、`config_version` 排除 api_key |
| **OOS** | 多环境 profile、配置热重载、密钥托管 |

### 3.2 契约（models）

| 项 | 内容 |
|---|---|
| **本阶段目标** | 33 个契约模型与 guide/ADR 一致，字段禁止漂移 |
| **DoD** | ① `tests/contract/test_models_vs_guide.py` 绿；② `ContractModel` 为 `extra=forbid + frozen`；③ `claims` 中 `supported/contradicted` 必须有引用 |
| **重难点** | 模型演进必须走 ADR；`GuardVerdict` 字段名曾漂移（已修正） |
| **OOS** | JSON Schema 导出、OpenAPI 反向生成模型 |

### 3.3 数据库（db）

| 项 | 内容 |
|---|---|
| **本阶段目标** | 24 表 + 迁移可重放 + 事件 seq 并发安全 + 幂等键可用 |
| **DoD** | ① `db upgrade` 幂等（跑两次无变化）；② `test_seq_concurrency` 绿；③ `verify_schema` 无 missing；④ `store_meta` 三行身份齐全 |
| **重难点** | `BEGIN IMMEDIATE` 仅写路径、WAL、部分唯一索引、`merged_ids_json` 派生字段不被源覆盖 |
| **OOS** | 多写进程、表分区、软删除 |

### 3.4 事件总线（runtime/events）

| 项 | 内容 |
|---|---|
| **本阶段目标** | 事件即真相源：seq 连续、去重不跳号、可回放、可导出 |
| **DoD** | ① `test_events_replay` 绿；② 同 `dedupe_key` 只落一条；③ 冲突时 `seq` 不空转；④ SSE 只消费库内事件 |
| **重难点** | 并发分配 seq、去重与冲突的区分、**流式帧不落库** |
| **OOS** | 跨库事件复制、事件压缩归档 |

### 3.5 三库（stores）

| 项 | 内容 |
|---|---|
| **本阶段目标** | Kuzu/Qdrant/文件可重建、可对账、可判死 |
| **DoD** | ① `stores verify` 在 100 篇真实数据上 `ok=True`，三方计数相等；② **collection 缺失时 verify 必须失败**（不得自动建空库）；③ `rebuild --verify` 幂等（两次边数不变） |
| **重难点** | Kuzu 只在 `close()` 落盘；`MERGE` 不得带易变属性（曾导致边翻倍）；Qdrant 本地模式告警与关闭 |
| **OOS** | 增量索引、向量库分片、GPU 加速 |

### 3.6 源适配（sources）

| 项 | 内容 |
|---|---|
| **本阶段目标** | 至少一条**真实数据源**端到端可用（arXiv），OpenAlex 可用但需 key；同步幂等 |
| **DoD** | ① arXiv selector → `sync` 100 篇入库、`new=0`（第二次）；② 无 selector → `E_SRC_NO_SELECTOR`；③ 401/403 → `E_SRC_AUTH`（不再 `E_SRC_4XX`）；④ 默认 90 天窗口（无 `from_year` 时）；⑤ **去重不得合并"只差数字"的标题**（`GPT-3` vs `GPT-4`） |
| **重难点** | 免费配额（无 key 共享池 → 401）、首拉全量历史、digit-token 相似度陷阱、单源 vs 多源 |
| **OOS** | 多源并行同步（P4）、PubMed/Semantic Scholar、全量历史回填 |

### 3.7 解析（parsing）

| 项 | 内容 |
|---|---|
| **本阶段目标** | PDF → 文本 → 分块（token 预算），失败可隔离 |
| **DoD** | ① 真实 PDF `ok=1` 且 `n_chunks≥1`；② 坏 PDF `failed=1` 不抛异常；③ 已解析不重复；④ 块 token ≤ 预算 |
| **重难点** | PyMuPDF/pdfplumber 双通道降级、tiktoken 离线回退 |
| **OOS** | 版面分析（表格/公式）、扫描件 OCR |

### 3.8 网关（gateway）

| 项 | 内容 |
|---|---|
| **本阶段目标** | 单一 LLM 出口：敏感不出网、缓存可复现、截断可恢复、成本可计量 |
| **DoD** | ① 敏感样本 `completer` 调用 0 次；② 二次调用 `cached=True & cost=0` 且内容一致；③ 截断 `max_tokens` 翻倍重试一次；④ 预算耗尽时**调用前**抛 `E_BUDGET_COST`；⑤ `llm_calls` 落库且 `cost_estimated` 标注 |
| **重难点** | 缓存键含 prompt/温度/上限；`finish_reason=length` 与空正文都算失败；预算是"调用前判" |
| **OOS** | 熔断器（breaker）、多 provider 路由、流式 token 计费 |

### 3.9 Harness 图（graph）

| 项 | 内容 |
|---|---|
| **本阶段目标** | LangGraph 主干可跑（4 节点）、checkpoint 可续、守卫纯判定 |
| **DoD** | ① 冒烟图 `intake→retrieve→draft` 顺序正确；② `invoke(None)` 不重放；③ E1–E13 常量齐全，回退边显式 `E_FEATURE_DISABLED`；④ 守卫只返回判决、不写事件 |
| **重难点** | 续跑只能 `invoke(None)`；节点必须幂等；守卫看**累计**产出而非单步 |
| **OOS** | S0–S9 全边、条件回退、子图 |

### 3.10 运行时（runtime）

| 项 | 内容 |
|---|---|
| **本阶段目标** | 一次 run 可跑通（真实数据）、失败可见、锁不泄漏、预算三维 |
| **DoD** | ① `run-topic` 成功：`intake→ingest→curate→report` 四阶段 + `report_written`；② 失败 → 失败报告四要素 + `error` 事件 + `failed`；③ 同 topic 并发 → `E_LOCK_HELD`；④ 非预期异常释放锁；⑤ 报告与事件**同事务** |
| **重难点** | 阶段顺序副作用、异常路径的锁释放、报告幂等（`content_sha`） |
| **OOS** | 异步任务队列、跨进程锁、断点重跑调度 |

### 3.11 Agent（agents）

| 项 | 内容 |
|---|---|
| **本阶段目标** | 只有 `reporter` 与 `base` 是**实现**；其余 5 个角色是**显式骨架** |
| **DoD** | ① 报告渲染确定性（正/逆序逐字节一致）；② 每条 claim 带 citation；③ 空证据 → 1 条 `unsupported` 且 `degraded=True`；④ LLM 摘要可选、失败降级、成本进同一预算；⑤ 其余 5 模块调用 → `E_FEATURE_DISABLED` |
| **重难点** | 不能"丢弃无引用内容"（会伪造 grounding）；摘要重算 `content_sha` |
| **OOS** | analyst/critic/mapper/retrieval/chat（P2/P3） |

### 3.12 上下文（context）

| 项 | 内容 |
|---|---|
| **本阶段目标** | token 预算裁剪 + 槽位注册 + 策略显式 |
| **DoD** | ① `fit_text` 不超预算；② `folding_for("summarize")` → `E_FEATURE_DISABLED`；③ 槽位重名/未知报错；④ 渲染按优先级确定性 |
| **重难点** | 保留引用锚点；注入上下文需**物化进事件**（P3 才做） |
| **OOS** | 摘要折叠、分层折叠、注入物化 |

### 3.13 工具（tools）

| 项 | 内容 |
|---|---|
| **本阶段目标** | 注册表 + 2 个内置工具（openalex_search / kv_cache）；超时可读 |
| **DoD** | ① 重名/未知工具报错；② 工具异常 → `ToolResult(ok=False)`；③ 超时 → `E_SRC_TIMEOUT` 且不挂死；④ kv_cache 往返 |
| **重难点** | 工具失败不得炸 run；超时用线程池而非信号 |
| **OOS** | MCP 适配、paper_pdf、工具权限 |

### 3.14 API（api）

| 项 | 内容 |
|---|---|
| **本阶段目标** | 8 组路由可用、错误码语义化、SSE 可续、OpenAPI 可导出 |
| **DoD** | ① `tests/integration/test_api.py` 绿；② 未知 run → 404；③ chat/graph → **501**；④ SSE `after_seq` 不重不漏、终态 `end`；⑤ `api export-openapi` 产出 ≥16 路径 |
| **重难点** | 501 vs 404 的语义、SSE 从库补发、同步执行与 202 的偏差 |
| **OOS** | 异步 run、鉴权、多用户、chat/graph 实装 |

### 3.15 评测（eval）

| 项 | 内容 |
|---|---|
| **本阶段目标** | 5 项指标可算、可复算、可导出；judge/gold 为骨架 |
| **DoD** | ① 分母 0 → `None`（不是 0.0）；② `persist_run_metrics` 重复调用行数不增；③ json/csv/md 三格式可读；④ `compute_run_metrics` 与报告口径一致 |
| **重难点** | 口径固定（grounding/hallucination/coverage/dedup/cost）、指标不得依赖写路径 |
| **OOS** | judge、gold 集、faultinject、datasets（P5） |

### 3.16 前端（web）

| 项 | 内容 |
|---|---|
| **本阶段目标** | 三页签可构建、Run 后自动出报告、Chat 显示 501（**技术栈已定 Vue 3**） |
| **DoD** | ① `cd web && npm run build` 成功且 `dist/` 产出；② Run 后自动加载报告（无需手填 run_id）；③ 事件时间线显示 seq/type/stage 与 payload；④ Chat 显示 501 说明 |
| **重难点** | 本阶段是**简化运行版**（单 `App.vue` + 组合式 API）；规范化（TS + Element Plus + 三独立视图 + 路由 + e2e）整体顺延 Phase 1.2 |
| **OOS** | TS、Element Plus、三独立路由页面、浏览器 e2e → **全部顺延 Phase 1.2（G-04/G-05）** |

### 3.17 文档与收口（docs）

| 项 | 内容 |
|---|---|
| **本阶段目标** | 三份事实文档定稿 + 缺口登记册 + 格式冻结 ADR |
| **DoD** | ① `RESULTS-P1.md` 数字与基线一致；② `phase1.1-known-gaps.md` 存在且每条有级别/归属；③ `adr/0006-*.md` 存在；④ `phase1-exit-checklist.md` 的 10 条命令全部可执行 |
| **重难点** | 文档数字必须由命令生成而非手写 |
| **OOS** | guide 全量重写、论文成稿 |

---

## 4. 缺陷分级与处置

| 级别 | 定义 | Phase 1.1 处置 |
|---|---|---|
| **P0 阻塞** | ① 出口断言红；② 数据错误（如 authors 丢失）；③ 违反契约（如 501 变 404） | **必须修** |
| **P1 可用性** | 有 workaround，或影响体验但不影响结论 | 选做（仅在 F 步骤内） |
| **P2 改进** | 未实现功能、性能、美化、重构 | **一律延后**，进 §5 |

> **"未实现"≠"缺陷"**：12 个骨架模块是**设计上的显式未实现**，不在修复范围。

---

## 5. 已知缺口登记册（Out-of-Scope 与 P 级）

| ID | 缺口 | 级别 | 归属 | 说明 |
|---|---|---|---|---|
| G-01 | ~~`upsert_many` 不写 `authors`/`paper_authorships`（100 篇真实论文 authors=0）~~ | ~~P0~~ **已关闭 2026-10-20** | F2 ✅ | 真实数据 authors=556 / links=564；回归门已加进 `verify_phase1.py` |
| G-02 | `guide` §3.6 差异登记未回写、ADR 索引未补 0004/0005 链接 | P1 | F8 | 纯文档 |
| G-03 | ~~缺 ADR-0006（事件/表格式 v1 冻结 + 变更流程）~~ | ~~P1~~ **已关闭 2026-10-20** | F8 ✅ | `adr/0006-event-and-schema-format-freeze.md`（D1 冻结 + D2 相邻迁移） |
| G-04 | 前端无 TS / 无 Element Plus / 单文件三页签 | P2 | **Phase 1.2**（技术栈已定 Vue 3） | 不影响功能 |
| G-05 | 无浏览器 e2e（Playwright） | P2 | **Phase 1.2** | API 层 e2e 已有 |
| G-06 | ~~`E_NOT_FOUND` 未引入（现用 `E_CONFIG_INVALID`→404）~~ | ~~P1~~ **已关闭 2026-10-20** | F3 ✅ | 404/400 语义分离；错误码表 100% 覆盖 |
| G-07 | ~~`sources sync` 无 CLI（只有 Python 调用与 API）~~ | ~~P1~~ **已关闭 2026-10-20** | F4 ✅ | `sources sync --topic --limit`；返回值带 `source` |
| G-08 | 单源同步（openalex 优先，否则取一个），无多源合并 | P2 | P4 | 需合并口径 |
| G-09 | `venue_ids` 未解析进 `config/seeds/topics.yaml` | P2 | P4 | arXiv 可绕过 |
| G-10 | 12 个骨架模块（agents×5、eval×4、breaker、mcp_adapter、paper_pdf） | P2 | P2–P5 | 显式未实现 |
| G-11 | `gateway/breaker.py` 熔断未实现 | P2 | P2 | 无 key 时无意义 |
| G-12 | run 同步执行（未异步 + 202） | P2 | P2 | 已有阻塞语义 |
| G-13 | ~~`phase2-implementation-steps.md` 不存在~~ | ~~P1~~ **已关闭 2026-10-20** | F9 ✅ | 首版含入口条件、12 骨架清单、P2-1…P2-6、7 条 DoD |
| G-14 | ~~SSE 未做"断线重连不重不漏"测试~~ | ~~P1~~ **已关闭 2026-10-20** | F7 ✅ | 分页/Last-Event-ID/重连 5 例契约测试 |
| G-15 | `stocks` 无（无需） | — | — | — |
| G-16 | ~~结构快照未纳入自动流程~~ | ~~P1~~ **已关闭 2026-10-20** | F8 ✅ | `phase1-doctor-snapshot.json` + F10 复核刷新 |

---

## 6. 修复步骤 F1–F10（严格顺序执行）

> **本阶段执行 9 步**：F1、F2、F3、F4、F5、F7、F8、F9、F10（**F6 已顺延 Phase 1.2**，见其条目）。
> 每一步都是"**可独立验收 + 可回滚**"的批次。你按顺序让我做，我做一步、跑一次基线、报一次红绿。

### F1 · 冻结与基线（0.5 d）✅ 完成 2026-10-20
- **动作**：新建 `scripts/verify_phase1.py`（10 条断言，`--offline/--online`）；写 `docs/implementation/phase1-exit-checklist.md`；跑一次生成红绿表；`doctor --json` 存档结构快照。
- **验收**：`verify_phase1.py --offline` 运行成功（允许 1–2 条红）；红绿表落盘。
- **禁止**：本步不改任何业务代码。
- **完成记录**：离线 **11/11 PASS**、在线 **13/13 PASS**（真实 arXiv `102/102/102`）；产出 `phase1-verify-report{,-online}.json`、`phase1-doctor-snapshot.json`；期间修正的 4 处问题全部在验证器内部（未触碰业务代码）。

### F2 · 修 P0：作者持久化（0.5 d）✅ 完成 2026-10-20
- **动作**：`upsert_many` 之后写 `authors` + `paper_authors`（幂等：`ON CONFLICT DO UPDATE`），补测试。
- **验收**：真实论文 `authors>0`；图谱作者节点 >0；全量测试绿。
- **禁止**：不得改 `Paper` 模型字段。
- **完成记录**：新增 `tests/integration/test_author_persistence.py`（3 例：写入 / 幂等 / 进图）；真实数据 **authors=556、links=564（papers=102）**；`verify_phase1.py --online` 增加 G-01 回归门（papers>0 而 authors=0 直接 FAIL）；全量 **233 passed**、ruff clean。

### F3 · 错误码与契约收口（0.5 d）✅ 完成 2026-10-20
- **动作**：引入 `E_NOT_FOUND`（404）；`docs/` 错误码表补 `E_SRC_AUTH`、`E_NOT_FOUND`、`E_VECTOR_COLLECTION_MISSING`；`action_for()` 全覆盖。
- **验收**：`curl /api/runs/nope` → 404 且 `code=E_NOT_FOUND`；`tests/unit/test_errors.py` 绿。
- **完成记录**：新增 `E_NOT_FOUND`（404）并把 `E_CONFIG_INVALID` 改为 **400**（语义分离）；补全 `CODE_RETRYABLE` 中缺失的 **24 个** 错误码（此前靠 `.get(code, False)` 兜底）；新增两条契约测试（全码覆盖 + 404/400 映射）；guide 错误表补 3 行；`pytest 235 passed`、ruff clean。

### F4 · 同步口径收口（0.5 d）✅ 完成 2026-10-20
- **动作**：`lit-agent sources sync --topic <id> [--limit N]` CLI；返回值增加 `source`；文档写明"单源分派"语义。
- **验收**：CLI 对 arXiv topic 拉到 100 篇；二次 `new=0`；无 selector → `E_SRC_NO_SELECTOR`。
- **完成记录**：CLI 已有 `--topic/--limit`，本步补**契约测试** 3 例（参数透传、缺 `--topic` 非零退出、无 selector 非零退出）；确认返回体含 `source`（单源分派可观测）；**单源语义**：配了 `openalex` 就用它，否则取字典序第一个源，多源合并留给 P4（G-08）；真实抓取验收由 `verify_phase1.py --online` 覆盖（papers=102、二次 `new=0`）。`pytest 238 passed`、ruff clean。

### F5 · 报告与指标一致性（0.5 d）✅ 完成 2026-10-20
- **动作**：`compute_run_metrics` 增加 `claims_total / claims_supported`；报告 sha 稳定性测试（同数据两次一致）。
- **验收**：`pytest -k "metrics or report"` 绿；两次 run 的 `content_sha` 相等。
- **完成记录**：**发现并修掉一个真不一致**——runner 只写 `reports.claims_json`，从不写 `claims` 表，导致指标 `claims=0`（报告却声称有 N 条）。新增 `_persist_claims()`：报告与 claims/citations 在同一事务落库（幂等）。指标新增 `claims_total/claims_supported` 并与报告 `n_claims` 对齐断言；补 3 例测试（对齐、sha 稳定、持久化可复算）；同步修正 2 个受影响的旧测试口径。`verify_phase1` 现报 `metrics claims=4 rows=11`。

### F6 · 前端规范化（**顺延 Phase 1.2**，本阶段不做）
- **决策**：技术栈定为 **Vue 3**；TS + Element Plus + 三独立视图 + 路由 + 浏览器 e2e 整体顺延。
- **本阶段前端只保留**：现有可构建的三页签版本（`npm run build` 通过即算满足 §3.16 DoD）。
- **Phase 1.2 验收**（预告，不在本阶段执行）：`vue-tsc` 无错、三独立路由可导航、Playwright 走通 Run→Report。

### F7 · API/SSE 补测（0.5 d）✅ 完成 2026-10-20
- **动作**：补 `after_seq` 不重不漏、`Last-Event-ID`、断线重连、501/404 契约测试。
- **验收**：`pytest -q tests/integration/test_api.py` 绿，新增 ≥4 例。
- **完成记录**：新增 `tests/integration/test_sse_contract.py` **5 例**：①分页 `after_seq` 不重不漏（`[1,2,3]` + `4..N` 恰好覆盖全集）；②`Last-Event-ID: 3` → 首条为 `id: 4`；③从倒数第二条重连只补发 1 条；④`after_seq` 超出末尾 → 只发 `event: end`、不带 `id:`；⑤并发 run → **409 `E_LOCK_HELD`**。全量测试绿、ruff clean。

### F8 · 文档三件套（0.5 d）✅ 完成 2026-10-20
- **动作**：RESULTS 定稿（数字由命令生成）；`phase1.1-known-gaps.md`；`adr/0006-event-and-schema-format-freeze.md`；guide §3.6 差异登记回写。
- **验收**：三份文件存在且与基线数字一致。
- **完成记录**：新增 ADR-0006（D1 `run_events` v1 冻结 + D2 相邻迁移，含变更登记表）与 `phase1.1-known-gaps.md`（分级、已关闭 5 条、开放 8 条、5 项实现偏差、新增流程）。**guide §3.6 逐条回写仍未做**（G-02，P1）——差异已在 known-gaps §4 汇总，不影响判据。

### F9 · 骨架登记与 Phase 2 接口（0.5 d）✅ 完成 2026-10-20
- **动作**：生成 12 骨架清单表（模块 / FEATURE 名 / 目标 Phase）；写 `phase2-implementation-steps.md` 首版（含出口标准，不写实现）。
- **验收**：两文件存在；骨架数量与代码一致（13 命中含 errors.py 常量，实为 12）。
- **完成记录**：`phase2-implementation-steps.md` v0.1.0 产出：入口条件 E1–E4、**12 骨架表**（`agents.*` 5、`eval.*` 4、`gateway.breaker`、`tools.*` 2）、P2-1…P2-6 六条工作流（每条含可执行出口标准 + 禁止项）、7 条 DoD（H1–H7）、不做清单与风险对策；骨架 FEATURE 名由命令枚举（非手写）。

### F10 · 基线复核（0.5 d）✅ 完成 2026-10-20
- **动作**：全量 G1–G6 跑一遍；更新 RESULTS 数字；打 tag（**由你执行**）。
- **验收**：G1–G6 全绿；tag 存在；本文件 §5 的 P0 全部关闭。
- **完成记录**：G1 `246 例/30 文件全绿`、G2 `ruff clean`、G3 `129/129 + schema 1.0 + 24 表`、G4 `11/11`、G5 `13/13（102/102/102, authors=556）`、G6 三份文档齐备；`phase1-doctor-snapshot.json` 已刷新；RESULTS-P1 新增 §4.5 复核表。**tag 未打**（我不执行 git 写操作，需你运行 `git tag phase1-rc1`）。

---

## 附录 A · Phase 1.1 关闭判定

按 §2 反向定义，Phase 1.1 **可以关闭**，依据：

1. G1–G6 全绿（上表有命令与输出）；
2. §5 中 **P0 全部关闭**（唯一 P0 为 G-01，已由 F2 修复并加回归门）；
3. 未做项均为 **P1/P2 且已登记**（`phase1.1-known-gaps.md`），不阻塞本阶段；
4. 具备可回退基线（`verify_phase1 --online` 13/13 + 建议 tag `phase1-rc1`）。

> 后续若发现新问题：按 §8 变更控制处理——**登记 → 分级 → 排入后续阶段**，不重新打开 Phase 1.1（除出现新的 P0，那需要单独立项）。

---

## 7. 出口总表（D1–D10 → 命令）

| # | 判据 | 命令 | 期望 |
|---|---|---|---|
| D1 | 结构完整 | `uv run python scripts/check_structure.py` | 129/129 |
| D2 | 测试与静态 | `uv run pytest -q`；`uv run ruff check .` | ≥230 passed；clean |
| D3 | 骨架显式失败 | `pytest -q tests/unit/test_surface.py` | 绿，且 12 模块抛 `E_FEATURE_DISABLED` |
| D4 | 幂等 | `verify_phase1.py --online` 的 `idempotent` 断言 | papers 增长 0、report sha 相同 |
| D5 | 事件回放 | `pytest -q tests/integration/test_events_replay.py` | 绿 |
| D6 | 三库对账 | `verify_phase1.py --online` 的 `stores` 断言 | `ok=True`、100/100/100 |
| D7 | 端到端 | `verify_phase1.py --online` 的 `e2e` 断言 | 真实论文 → 报告带引用 |
| D8 | 成本计量 | `pytest -q tests/integration/test_llm_report.py` | 绿（成本进同一预算） |
| D9 | 失败可见 | `pytest -q tests/integration/test_runner.py -k fail` | 绿 |
| D10 | 文档 | 文件存在性检查 | RESULTS/ADR-0006/known-gaps |

---

## 8. 变更控制

### 变更记录

| 版本 | 日期 | 变更 | 原因 |
|---|---|---|---|
| 1.1.0 | 2026-10-19 | 首版：三规则、17 模块 DoD、16 条缺口、F1–F10 | 终止"无边界修复" |
| **1.1.1** | 2026-10-19 | ① 确认接受 §2 反向定义；② **F6 顺延 Phase 1.2**（前端技术栈定为 Vue 3）；③ G-04/G-05 级别 P1→P2、归属改为 Phase 1.2；④ 本阶段工作量 5.5→**4.5 人日**（9 步） | 项目负责人决策：先拿"可运行系统"，前端规范化后置 |

1. 任何新增需求 → 写入 §5（给定 ID、级别、归属阶段），**不得直接开工**。
2. 任何对 §3 判据的修改 → 升版本号（1.1.1、1.1.2…），并在本节记录"改了什么、为什么"。
3. 每完成一步 F，需在 §6 该步下追加一行：`完成日期 / 验收命令输出摘要 / 新增测试数`。
4. Phase 1.1 关闭后，本文档只允许"追加"，不允许"改写判据"。

---

## 9. 命令速查

```powershell
. .\scripts\env.ps1
uv run pytest -q
uv run ruff check .
uv run python scripts/check_structure.py
.\scripts\lit-agent.ps1 doctor
.\scripts\lit-agent.ps1 db status
.\scripts\lit-agent.ps1 stores verify
uv run python scripts/verify_phase1.py --offline
uv run python scripts/verify_phase1.py --online
cd web; npm run build
```
