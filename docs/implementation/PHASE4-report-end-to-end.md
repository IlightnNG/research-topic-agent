# Phase 4 · Report 全流程完整运行

> 版本：1.0（2026-10-31）
> 类型：总方向 / 指导方案
> 范围：Report 端到端；Chat 不在本 phase
> 状态：planning
> 依据：`docs/ARCHITECTURE.md`、`docs/TODO.md`、真实 100 篇审计
> 原则：一个 phase 只改一个模块；接口先冻结；LLM 只做适合 LLM 的事。

---

## 1. 目标

从当前：

```text
100 篇 → 3 方向 → 模板报告 → degraded → reject
```

做到：

```text
100 篇
→ policy band 个可解释方向
→ 每方向 EvidencePack
→ LLM 分方向写作
→ code gate + verifier + score
→ 全局 overview/comparison/gaps
→ 全量一致性检查
→ complete/degraded 明确
→ API/UI 可读
```

**Phase 4 完成的定义**：

1. 100 篇真实论文可跑完整 Report Workflow；
2. 动态方向数，每方向 ≥ policy.min_size；
3. 每方向正文覆盖该方向 ≥80% claims；
4. 不再出现作者列表 claim；
5. 全报告 claim 计数一致；
6. Paper Index 有 title/venue/year；
7. 至少 30% 全文，或明确 degraded；
8. LLM 参与 claim、方向命名、section 写作、overview/comparison；
9. 独立 verifier + scorecard；
10. API 返回报告，最小 UI 可读；
11. 真实 100 篇审计从 reject 提升到 pass 或明确 degraded。

---

## 2. 非目标

Phase 4 不做：

- Chat 新功能；
- 生产级前端；
- 多用户/权限；
- 自动调参闭环；
- 论文全文下载法律合规以外的采集扩展；
- 旧系统兼容。

Chat 在后续 phase 单独处理。

---

## 3. 当前基线

| 项 | 当前 |
|---|---|
| 真实论文 | 100 篇 OpenAlex |
| 全文 | 5 篇（5%） |
| claims | 185，含作者列表 |
| 方向 | 3，max_share 0.86 |
| 报告 | 2519 words，degraded |
| LLM 审计 | reject |
| 评分 | coverage 2 / synthesis 1 / insight 1 |
| 测试 | 23 v2 tests |

---

## 4. 目标链路

```text
RunShell
  → source
  → evidence
  → map
  → report_plan
  → per-direction writer
      EvidencePack
      → LLM section
      → code gate
      → verifier
      → section score
      → append
  → global writer
      overview
      comparison
      gaps
  → full consistency check
  → persist
  → API/UI
```

### 4.1 ReportPlan

只决定结构，不写内容：

```json
{
  "title": "...",
  "sections": [
    {"id": "overview", "kind": "overview"},
    {"id": "D1", "kind": "deep_dive", "paper_ids": ["..."]},
    {"id": "comparison", "kind": "comparison"},
    {"id": "gaps", "kind": "gaps"},
    {"id": "method", "kind": "method"},
    {"id": "index", "kind": "paper_index"}
  ]
}
```

### 4.2 EvidencePack

每个方向只拿自己的证据：

```json
{
  "direction": {"id": "D1", "name": "...", "paper_ids": ["..."]},
  "papers": [{"paper_id": "...", "title": "...", "abstract": "..."}],
  "claims": [{"claim_id": "...", "text": "...", "quote": "...", "type": "finding"}],
  "quotes": [{"paper_id": "...", "text": "...", "section": "...", "page": 1}]
}
```

### 4.3 SectionArtifact

```json
{
  "section_id": "D1",
  "kind": "deep_dive",
  "title": "...",
  "body": "...",
  "claim_ids": ["..."],
  "common_ground": [],
  "differences": [],
  "open_questions": [],
  "state": "accepted|repaired|failed"
}
```

---

## 5. LLM 使用位置

| 位置 | 用 LLM | 不用 LLM |
|---|---|---|
| source query 扩展 | ✅ | — |
| metadata 解析 | — | ✅ |
| claim 抽取 | ✅ | quote 校验 ✅ |
| claim 类型 | ✅ | 规则过滤 ✅ |
| 方向命名 | ✅ | 聚类 ✅ |
| direction section | ✅ | count gate ✅ |
| comparison 正文 | ✅ | matrix 表格 ✅ |
| overview | ✅ | 计数 ✅ |
| gaps | ✅ | 覆盖统计 ✅ |
| verifier | ✅ | schema/quote gate ✅ |
| judge | ✅ | hard gate ✅ |
| Paper Index | — | ✅ |

原则：

- LLM 不生成无证据事实；
- LLM 不替代精确计数；
- LLM 输出必须 JSON schema；
- LLM 失败必须有 deterministic fallback；
- 所有 LLM 调用记录 prompt_version/model/tokens/cost。

---

## 5.5 Contract gate（M4-P02 前必须完成）

```text
C0 冻结 docs/CONTRACTS.md v1.0
C1 contracts/ 包
C2 ports
C3 composition.py
C4 ReportWorkflow 依赖注入
C5 ReportRepository
C6 EvalRunner 注入
C7 API application port
C8 contract tests + import guard
C9 删除旧 contracts
```

M1-P01 可在 C0 前开始，但 M4-P02 不得在 C1–C4 前开始。

详见 `docs/CONTRACTS.md`。

## 6. Phase 计划

严格顺序：

```text
1. M1-P01  Kernel ReAct + LLM client + step checkpoint
2. M3-P01  Claim 质量 + 类型 + 作者过滤
3. M2-P01  Metadata + 全文 30%
4. M4-P01  方向质量 + 计数一致
5. M4-P02  分方向 LLM writer + 全局章节
6. M5-P01  Scorecard + LLM judge
7. M6-P01  Report API + 最小 UI
```

依赖：

```text
M1 → M3
M1 → M2
M3 + M2 → M4-P01
M4-P01 → M4-P02
M4-P02 → M5
M4-P02 → M6
```

可并行：

```text
M3 与 M2 在 M1 后并行
M5 与 M6 在 M4-P02 后并行
```

---

## 7. 全局契约

### 7.1 共享

```text
contracts.py                  RunRequest/NodeSpec/State
domains/report/contracts.py   Source/Evidence/Map/Report
```

Phase 4 新增：

```text
ReportPlan
EvidencePack
SectionArtifact
ScoreCard
```

### 7.2 版本

所有 artifact 加：

```json
{"schema_version": 2}
```

旧 v1 不兼容；v2 内部迁移。

### 7.3 错误

统一使用 `docs/ERRORS.md` 的 code；不再抛裸 RuntimeError 到 API。

### 7.4 事件

新增：

```text
plan.created
section.started
section.finished
section.rejected
report.consistency_failed
report.scored
```

字段见 `docs/LOGGING.md`。

---

## 8. 全局验收

### H1–H8 结构

```text
H1 100 篇跑完
H2 policy band 方向
H3 每方向 ≥3 篇
H4 max_share ≤0.6
H5 每方向正文 claim coverage ≥0.8
H6 全报告计数一致
H7 paper index metadata 完整
H8 无作者列表/截断 claim
```

### H9–H14 内容

```text
H9 section 由 LLM 生成
H10 comparison 有正文
H11 overview 计数正确
H12 gaps 来自证据
H13 verifier accept
H14 citation coverage=1
```

### H15–H18 运行

```text
H15 每 section 可重试
H16 pause/resume 可用
H17 API 可读报告
H18 最小 UI 可读
```

### 评分

```text
complete 必须同时满足：
  fulltext >=0.3
  policy band 方向
  min size>=3
  max_share<=0.6
  policy word range
  claim coverage>=0.8
  citation coverage=1
  uncited facts=0
  verifier accept
```

否则 `degraded`；硬门禁失败 `failed`。

---

## 9. 测试策略

```text
M1：fake LLM + step checkpoint
M2：OpenAlex/PDF fixture + 真实 20 篇
M3：作者列表/截断/类型 fixture
M4：方向 fixture + 50 篇全链路
M5：公式/scorecard/judge fixture
M6：API + SSE + UI e2e
```

Live gate：

```text
20 篇 → 50 篇 → 100 篇
```

每阶段都跑 LLM audit；不通过不得进入下一 phase。

---

## 10. 风险

| 风险 | 缓解 |
|---|---|
| LLM 幻觉 | quote gate + verifier |
| 方向仍塌缩 | 真实 embedding / 条件降级 |
| 全文不足 | 多源 + 明确 degraded |
| token 成本 | section 级预算/缓存 |
| section 覆盖不足 | claim pack + coverage gate |
| 评分 gaming | 只算正文引用，不认 ledger |
| 接口漂移 | contract tests |

---

## 11. 交付物

```text
docs/implementation/PHASE4-report-end-to-end.md
docs/modules/m1-engine/M1-P01-kernel-react-and-llm.md
docs/modules/m3-evidence/M3-P01-claim-quality.md
docs/modules/m2-source/M2-P01-metadata-and-fulltext.md
docs/modules/m4-report/M4-P01-direction-and-counting.md
docs/modules/m4-report/M4-P02-modular-llm-writer.md
docs/modules/m5-evaluation/M5-P01-scorecards-and-judge.md
docs/modules/m6-interface/M6-P01-report-api-and-ui.md
```

每个 phase 收尾：

```text
一句话英文 commit
type(Mx-Pnn): summary
```

规范见 `docs/CONVENTIONS.md`。
