# Phase 3.3 · Report 质量、稳定性与可调参收尾

> **版本**：**1.1.0**（2026-10-29，S1–S2 已落地）
> **前置**：Phase 3.2 已收尾（生成链路、Tab 工作台、引用、PDF、作者、语言、分页）
> **目标**：把“能生成报告”推进到“报告相关、可读、稳定、可调参”
> **范围**：Source/Retrieval → PaperCard → Claim → Cluster → Synthesis → Validate → Report
> **不在范围**：Chat 流式/引用抽屉（3.4）、团队/全局图谱（P4）

---

## 0. 全量实跑证据（2026-10-29）

### 0.1 场景

- 新建 topic `ai-agents-live`；
- OpenAlex ACL（`S4363608652`）+ 2024 起 + limit 20；
- 无 OpenAlex key，抓取成功：`fetched=20, papers_new=20`；
- 数据库共 23 篇（20 篇 ACL + 3 篇 E2E fixture）。

### 0.2 报告结果

```text
claims = 32
sections = 7
words = 791
generated_by = llm
report = out/live-report-ai-agents-live.md
```

### 0.3 结论

**结构通过，内容不合格**：

| 现象 | 影响 |
|---|---|
| ACL 全 venue 抓取，混入 LlamaFactory、LongBench、F5-TTS | 报告与 topic 不相关 |
| 方向 `Models / Language`、`Annual / Association` | 聚类被 ACL/venue 词支配 |
| “published at ACL 2024”“作者列表”成为 claim | 书目信息污染结论 |
| 多次 `E_LLM_TRUNCATED` / `paper_card.llm_fallback` | 抽取不完整，报告质量随机 |
| 23 篇时 report 阶段偶发卡住（e2e 17/18） | 稳定性不足 |
| 缓存未写入（`write_cache=False`） | 每次重跑 LLM，成本高 |

**Phase 3.3 只解决这些“真实问题”，不再堆新 UI。**

---

## 1. 目标与非目标

### 目标

| # | 目标 | 可度量 |
|---|---|---|
| G1 | 报告与 topic 相关 | 人工抽检 ≥80% 论文相关 |
| G2 | 方向可读 | 方向名不含 venue/出版词；每方向 ≥2 篇 |
| G3 | claim 纯净 | 0 条书目/作者 claim |
| G4 | LLM 稳定 | 截断/解析失败 <5%；失败有回落 |
| G5 | 规模稳定 | 20/50/100 篇不卡死；超时可诊断 |
| G6 | 可调参 | 所有质量/成本参数进配置与实验脚本 |
| G7 | 可验收 | 单元 + live + e2e + 人工评分全绿 |

### 非目标

- Chat 流式/断线恢复（3.4）；
- 团队检测/全局图谱（P4）；
- 双 Tab 拖拽并列（P2，Open Issues）；
- 自动 PDF 下载/OCR（Open Issues）。

---

## 2. 目标链路

```text
Topic scope
  → ① Source suggest（AI 提名 + OpenAlex 解析 + 用户确认）
  → ② Retrieval（query/venue 过滤 + relevance 排序 + 预览）
  → ③ PaperCard（批量、缓存、quote、token 上限）
  → ④ Claim（纯度过滤、去重、claim_id）
  → ⑤ Cluster（去 boilerplate + embedding/质心 + LLM 命名）
  → ⑥ Synthesis（方向内共性/差异/问题，严格 claim_id）
  → ⑦ Assemble + Validate（section/claim/引用/语言/thin）
  → ⑧ Report（metadata：fallback_count、coverage、quality flags）
  → ⑨ Metrics/Lab（fallback、token、coherence、relevance）
```

### 2.1 运行位置

- Report 仍是外层 10 节点之一，内部子流水线；
- 不新增顶层节点；
- 子步骤通过 `phase_change.payload.step` 记录；
- 所有 LLM 调用必须能关联到 `run_id`（当前 `llm_calls.run_id` 为空，需修）。

---

## 3. 模块问题与改进

### M1 · Source / Retrieval（最高优先级）

**问题**

- selector 只有 `venue_ids`，空则 `E_SRC_NO_SELECTOR`；
- 有 venue 则抓整个 venue，**没有 topic 过滤**；
- 报告阶段不自动 sync，用户以为“生成报告=抓新论文”；
- 无 query/关键词过滤，ACL 全量论文都进来。

**改进**

1. selector 支持：
   ```json
   {"venue_ids":["S..."],"queries":["LLM agents tool use"],"from_year":2024}
   ```
2. OpenAlex 检索用 `search` 或 `title_and_abstract.search`；
3. 抓取后做 **scope relevance** 过滤（标题+摘要 embedding/关键词），保留 top-K；
4. 提供 `POST /api/sources/preview`：返回预计论文数 + 样例，用户确认；
5. 报告前若数据为空/过旧，明确提示“先同步源”，不静默空报告；
6. venue 自动建议（见 Open Issues OI-001）。

**验收**

- 同一 topic 的 top-20 中，人工判定相关 ≥16；
- 空 selector 时给出可操作的 `E_SRC_NO_SELECTOR` + 建议；
- 20 篇抓取 ≤30s（无 key）。

### M2 · PaperCard 预处理

**问题**

- 每篇一次 LLM 调用（20 篇=20 次），无批处理；
- `max_tokens=900` 偏小，导致 `E_LLM_TRUNCATED`；
- `write_cache=False` 后缓存完全没写，跨 run 重复成本；
- 无 JSON 截断修复；无 token/费用上限。

**改进**

1. 批处理：`batch_size=5`，一次抽 5 篇（严格 JSON 数组）；
2. `max_tokens_card` 配置（默认 1200），按论文长度动态；
3. 缓存写入改到 **run 提交后**（不要嵌套事务）：
   - `paper_cards` 写队列 / post-commit hook；
   - 同 `paper_id+content_sha` 命中直接复用；
4. JSON 截断 → 一次 repair（补全/缩短），仍失败则 deterministic；
5. 记录 `tokens/cost/latency/fallback_reason`。

**验收**

- 20 篇 ≤5 次 LLM 调用；
- 第二次同数据 run 的 LLM 调用数下降 ≥80%；
- 截断回落 <5%。

### M3 · Claim 抽取与纯度

**问题**

- claim 含“published at ACL”“作者列表”；
- 摘要短的论文只出 1 条，长论文可能重复；
- claim 超过上限被硬截断，可能丢关键结论。

**改进**

1. Prompt 明确：
   - 只抽 **research claims**（问题/方法/结果/局限）；
   - 禁止 venue、出版信息、作者、致谢、页数；
   - 无结果写 `null`，不补全；
2. 代码过滤：
   - 正则拒绝 `published at|proceedings|authors?|conference|journal` 等模式；
   - 要求 claim 含动词/结果，不是标题复述；
3. 每篇 2–3 条，按信息量排序，不做无意义截断；
4. 保留 quote/page，citation 必须可回指。

**验收**

- 人工抽检 20 条 claim，书目类 0；
- 每条 claim 有 citation + quote；
- 重复率 <10%。

### M4 · 方向聚类

**问题**

- Jaccard 词面聚类被 `ACL/Annual/Association/Proceedings` 支配；
- 方向名 `Models / Language`、`Annual / Association` 不可读；
- `label_directions` 因 120 tokens 截断而失败；
- 无 embedding，语义相似论文可能分开。

**改进**

1. 停用词表：venue/出版/作者类词（`acl, neurips, icml, annual, association, proceedings, conference, journal, paper, authors`）；
2. 向量：优先 embedding（可用现有向量库/模型）；无模型时 TF-IDF + 余弦，不只 Jaccard；
3. 聚类：Agglomerative / HDBSCAN，`min_cluster_size=2`，固定 seed；
4. 方向命名：
   - LLM 输入仅 cluster 内标题+claims；
   - `max_tokens=240`；
   - 失败用 top terms，但先过滤 boilerplate；
5. 记录 `cluster_version`、threshold、coherence。

**验收**

- 方向名不含 venue 词；
- 人工看 5 个方向，≥4 个可解释；
- 同方向内至少 2 篇。

### M5 · 方向综合

**问题**

- 部分方向 `report.synthesis.fallback`，仍标记 `generated_by=llm`；
- 对比句引用不足/方向泛化；
- 没有 fallback_count 元信息。

**改进**

1. `max_tokens_synthesis=1000`；
2. 输出 schema 校验（claim_ids 白名单、differences ≥2 引用）；
3. 失败逐方向回落，并记录 `fallback_count`；
4. `generated_by` 改为：
   - `llm`（全部成功）
   - `hybrid`（部分回落）
   - `template`（全回落）
5. 低质量方向（claims<2）不生成 deep dive。

**验收**

- 0 个方向“空壳”；
- `hybrid` 时报告 metadata 明示；
- 每方向至少有 common 或 differences。

### M6 · 组装与校验

**问题**

- 报告 791 字但 claim 32 条，密度失衡；
- 无 `thin`/`coverage` 元信息；
- 旧报告语言字段为空；
- section 内 claim 索引可能重复。

**改进**

1. 报告 metadata：
   ```json
   {"generated_by":"hybrid","fallback_count":3,"coverage":0.78,
    "thin":false,"cluster_version":"..."}
   ```
2. 校验：
   - 每 direction ≥2 篇；
   - claim 去重；
   - `[C#]` 可解析；
   - 书目 claim 拒绝；
   - 语言一致。
3. `thin` 条件：claims<5 或 words<300 或 papers<5；
4. 旧报告兼容：`language=null → en`。

**验收**

- 坏报告不落库；
- `thin=true` 时 UI 明确提示；
- 32 claims 时不再出现“标题/作者”段。

### M7 · 持久化、缓存与并发

**问题**

- 23 篇时 report 阶段偶发卡住（e2e 17/18）；
- `write_cache=False` 规避嵌套写锁，但缓存不生效；
- 无 run 级超时/中断诊断；
- 测试数据与 live 数据混在同一个 store。

**改进**

1. 缓存 **提交后写**：`commit_pending` 成功后异步/短事务写 `paper_cards`；
2. 报告阶段只读，不写业务表；
3. `report` 子步骤超时（`report.step_timeout_s`），超时降级模板；
4. run 卡住时记录 `E_REPORT_TIMEOUT`，允许 abort；
5. E2E 使用独立 store 或专用 topic，不依赖 live papers；
6. 增加 `report_steps` 真实写入（当前表未写）。

**验收**

- 23/50 篇重复跑 10 次无卡死；
- 超时能降级并留错误码；
- 缓存命中率可查。

### M8 · 指标与调参

**问题**

- `llm_calls.run_id` 为空，无法按 run 统计；
- 无 fallback_count / relevance / coherence；
- 参数散落，缺少实验脚本。

**改进**

1. 修 `llm_calls.run_id` 绑定；
2. 新增报告指标：
   `report_fallback_count`, `report_hybrid`, `report_relevance_proxy`,
   `cluster_coherence`, `claim_purity`, `cache_hit_rate`；
3. `scripts/tune_report.py`：
   - 参数矩阵；
   - 输出 CSV；
   - 固定 seed；
4. 报告页显示 `generated_by + fallback_count`。

**验收**

- 任意 run 可查 cost/tokens/fallbacks；
- 调参结果可复跑。

### M9 · 前端体验（仅修痛点）

| 问题 | 改进 |
|---|---|
| 卡住 run 无提示 | 显示 stage + 超时提示；允许 abort |
| `hybrid` 不可见 | Report 头部显示 `Generated by: hybrid (3 fallbacks)` |
| 无 run 删除 | 见 Open Issues OI-002 |
| 旧报告语言空 | 显示 Unknown，不崩 |
| 右侧 Outline | 见 Open Issues OI-003 |

---

## 4. 调参实验设计

### 4.1 数据集

| 集 | 规模 | 用途 |
|---|---|---|
| `ai-agents-live` | 20 篇 | 快速迭代 |
| `rag-live` | 50 篇 | 中等规模 |
| `acl-100` | 100 篇 | 压力/稳定性 |
| `fixture-3` | 3 篇 | 回归/降级 |

### 4.2 参数

```yaml
report:
  max_tokens_card: 1200
  max_tokens_cluster: 240
  max_tokens_synthesis: 1000
  batch_size: 5
  max_claims_per_paper: 3
  cluster_threshold: 0.18
  min_cluster_size: 2
  token_budget: 120000
  step_timeout_s: 120
  cache_write: post_commit
source:
  top_k: 20
  relevance_min: 0.2
  query_mode: search
retrieval:
  query_top_k: 40
```

### 4.3 指标

| 指标 | 目标 |
|---|---|
| `topic_relevance`（人工 20 篇抽检） | ≥0.8 |
| `claim_purity`（书目 claim 比例） | 0 |
| `citation_coverage` | 1.0 |
| `fallback_rate` | <0.05 |
| `cluster_coherence` | 越高越好，记录基线 |
| `report_words` | 600–1200 |
| `latency` | 20 篇 <90s |
| `cost` | 记录并对比 |

### 4.4 方法

1. **一次一参数**：先 token，再 batch，再 threshold；
2. 每个配置跑 3 次（固定 seed），取中位数；
3. 记录 `config_hash` 到报告；
4. 用 `scripts/tune_report.py` 输出：
   ```text
   config, papers, claims, fallback, relevance, words, latency, cost
   ```
5. 选 Pareto 点（质量/成本），不追求单指标最优。

---

## 5. 测试与验收

### 5.1 分层

| 层 | 内容 | 命令 |
|---|---|---|
| 单元 | 书目过滤、token、聚类停用词、fallback | `pytest -q tests/report` |
| API | source preview、run language、report metadata | `pytest -q tests/api` |
| 集成 | 20 篇 live（mock OpenAlex + fake gateway） | `pytest -q tests/report/test_live_pipeline.py` |
| E2E | 独立 store；Tab/引用/关闭/语言 | `npx playwright test` |
| 人工 | 20 条 claim、5 个方向 | 评分表 |

### 5.2 验收 H1–H15

| # | 判据 |
|---|---|
| H1 | 20 篇 top-20 相关 ≥16（人工） |
| H2 | 方向名不含 venue/出版词 |
| H3 | 书目 claim = 0 |
| H4 | 每条 claim 有 citation + quote |
| H5 | `fallback_rate < 5%` |
| H6 | `generated_by` 能区分 llm/hybrid/template |
| H7 | 报告 600–1200 words（20 篇） |
| H8 | 23 篇重复 10 次不卡死 |
| H9 | 超时能降级 + `E_REPORT_TIMEOUT` |
| H10 | 缓存二次 run 命中 ≥80% |
| H11 | en/zh 均生成，引用不变 |
| H12 | 旧报告可读 |
| H13 | E2E 18/18，独立 store |
| H14 | `pytest 601+` 全绿 |
| H15 | 参数实验可复跑（CSV） |

### 5.3 手工验收（30 分钟）

1. 创建 `ai-agents-live2`，AI 建议 venue → 确认；
2. 同步 20 篇，预览相关论文；
3. 生成英文报告：4–6 方向，无书目 claim；
4. 点引用 → Paper Tab；关闭；切中文再生成；
5. 同一数据再跑一次：缓存命中、成本下降；
6. 100 篇跑一次：不卡死；失败有错误码；
7. 查看 `generated_by/fallback_count`。

---

## 6. 实施步骤

| 步 | 内容 | 预估 |
|---|---|---|
| S1 ✅ | Source selector 支持 queries + preview | `build_search`、`/api/sources/preview`、`preview_selector` |
| S2 ✅ | AI venue 建议 + 人工确认 | `/api/sources/suggest`、`SourceSuggest.vue`、Topic 创建页 |
| S3 | 批量 PaperCard + token 配置 + JSON repair | 3d |
| S4 | 提交后缓存 + 缓存指标 | 2d |
| S5 | claim 纯度过滤 + prompt 修正 | 2d |
| S6 | 聚类停用词/embedding/命名 token | 3d |
| S7 | synthesis 健壮性 + hybrid 元信息 | 3d |
| S8 | thin/coverage/validate + 旧报告兼容 | 2d |
| S9 | 并发/超时/缓存/e2e 隔离 | 3d |
| S10 | 指标 + tune 脚本 + 20/50/100 实验 | 4d |
| S11 | 调参 + 报告质量人工评分 | 3d |
| S12 | 收尾 + 文档 + 回归 | 2d |

**总计 ≈ 33 人日。**

---

## 7. 风险与回滚

| 风险 | 缓解 |
|---|---|
| OpenAlex query 质量差 | 预览 + 人工确认；保留 venue 模式 |
| 聚类 embedding 依赖重 | 先 TF-IDF，embedding 可选 |
| token 成本上升 | 预算/批量/缓存；实验选 Pareto |
| 缓存写锁 | post-commit 异步；失败只告警 |
| 调参过拟合 | 固定测试集 + 人工抽检 |
| 回滚 | `report.v3_enabled=false` 回到 3.2 模板；迁移不回滚数据 |

---

## 8. 与其他文档

- 待解决问题：[docs/OPEN-ISSUES.md](../OPEN-ISSUES.md)
- 3.2 收尾：[phase3.2-report-quality.md](phase3.2-report-quality.md)
- 开源参考：[open-source-borrowing-survey.md](open-source-borrowing-survey.md)

---

## 9. 变更记录

| 版本 | 日期 | 内容 |
|---|---|---|
| 1.1.0 | 2026-10-29 | S1–S2 落地：selector queries、preview API、AI venue 建议 + 确认 UI；606 pytest / 18 e2e |
| 1.0.0 | 2026-10-29 | 首版：基于 20 篇实跑问题，M1–M9、调参实验、H1–H15、S1–S12 |
