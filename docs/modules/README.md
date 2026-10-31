# Modules · 模块地图

> 版本：1.0（2026-10-31）
> 目的：把系统拆成 **6 个可独立优化的模块**。后续每个模块单独写 phase，不同时改多个模块。
> 旧代码已移出仓库；旧模块名不再使用。

---

## 1. 模块列表

| ID | 模块 | 文件夹 | 代码路径 | 一句话职责 |
|---|---|---|---|---|
| **M1** | Engine | `docs/modules/m1-engine/` | `src/lit_agent_v2/{contracts,run_shell,workflow,kernel,storage}` | 运行生命周期、Workflow、Kernel、状态、事件、存储 |
| **M2** | Source | `docs/modules/m2-source/` | `src/lit_agent_v2/domains/report/{openalex,ingest,pdf,source}` | 检索、ingest、PDF、语料与 metadata |
| **M3** | Evidence | `docs/modules/m3-evidence/` | `src/lit_agent_v2/domains/report/{evidence,claim_extractor,contracts}` | 卡片、全文、claim、quote 校验 |
| **M4** | Report | `docs/modules/m4-report/` | `src/lit_agent_v2/domains/report/{map,write,persist,workflow}` | 方向、写作、组装、报告落库 |
| **M5** | Evaluation | `docs/modules/m5-evaluation/` | `src/lit_agent_v2/{metrics,evaluation}` | 指标、评分、数据集、judge、调参 |
| **M6** | Interface | `docs/modules/m6-interface/` | `src/lit_agent_v2/{api,cli,domains/chat}` | API、SSE、CLI、Chat、UI 契约 |

---

## 2. 依赖方向

```text
M1 Engine
  ↑ used by all

M2 Source
  ↓ SourceArtifact

M3 Evidence
  ↓ EvidenceArtifact

M4 Report
  ↓ ReportDraft / VerifiedReport

M5 Evaluation
  reads artifacts/metrics; never mutates report

M6 Interface
  calls M1 + M4 + M5 + M3 (read-only)
```

规则：

- 依赖只能向下，不能反向 import；
- M5 只读，不修改报告；
- M6 不直接写 DB，不绕过 M1；
- M4 不重新抓论文；
- M3 不做聚类/写作；
- M2 不抽 claim；
- M1 不 import domain 实现，只通过注册的 handler/workflow 调用。

---

## 3. 共享契约

共享契约放在 M1：

```text
contracts.py
  RunRequest / RunState / NodeSpec / WorkflowDefinition

domains/report/contracts.py
  SourceArtifact / EvidenceArtifact / MapArtifact / ReportDraft
```

修改契约：

1. 必须同时改 producer/consumer；
2. 必须升 `schema_version`；
3. 必须加 contract test；
4. 必须更新本文件；
5. 不允许“某个模块先改，其他以后适配”。

---

## 4. 模块 phase 命名

每个模块一个文件夹，phase 文档直接放在模块目录：

```text
docs/modules/m1-engine/M1-P01-run-shell.md
docs/modules/m1-engine/M1-P02-kernel-react.md
docs/modules/m3-evidence/M3-P01-claim-types.md
```

格式：

```text
^M[1-6]-P\d{2}-[a-z0-9-]+\.md$
```

- `M1`–`M6`：模块 ID；
- `P01`：两位 phase 序号，只增不改；
- slug：小写英文短横线，不超过 5 个词；
- 一个 phase 只改一个模块；
- phase 文档必须写：目标、边界、接口、指标、测试、验收、回滚。

---

## 5. Commit 标准

每个 phase 收尾只生成 **一句话英文 commit**：

```text
<type>(<module>-P<nn>): <summary>
```

示例：

```text
feat(M3-P01): add claim type validation and author-list rejection
fix(M4-P02): enforce claim-count reconciliation before publish
refactor(M1-P03): isolate checkpoint writer from workflow runner
test(M5-P01): add direction f1 fixture gate
docs(M2-P02): define openalex metadata contract
```

规则：

- 一行，不超过 72 字符；
- 英文，祈使句；
- 不以句号结尾；
- type：`feat|fix|refactor|test|docs|chore`；
- 必须带模块和 phase；
- 一个 commit 只对应一个 phase。

完整规范见 `docs/CONVENTIONS.md`。

---

## 6. 模块完成定义

一个模块 phase 只有同时满足以下条件才算完成：

```text
1. 只改本模块边界内的代码；
2. 接口契约有测试；
3. 模块指标有 gate；
4. 独立测试通过；
5. 至少一个集成测试通过；
6. 文档/STATUS/TODO 更新；
7. 没有 legacy import；
8. 生成一句话 commit。
```

不满足 → 不允许进入下一个 phase。

---

## 7. 当前模块状态

| 模块 | 状态 | 主要缺口 |
|---|---|---|
| M1 | 原型 | Workflow 有；Kernel 非完整 ReAct；pause 仅 Node 边界 |
| M2 | 原型 | OpenAlex/PDF 有；全文率 5%；无 arXiv 多源 |
| M3 | 原型 | claim 抽取不过滤作者；purity 恒 1 |
| M4 | 原型 | 确定性 writer；方向塌缩；计数不一致 |
| M5 | 原型 | 无 gold；无 LLM judge；评分简陋 |
| M6 | 原型 | API/Chat 可用；无生产 UI；旧前端已移出 |

TODO 见 `docs/TODO.md`。
