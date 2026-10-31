# Contracts & Module Communication

> 版本：1.2 FROZEN（2026-10-31）
> CONTRACT_VERSION=1.2 · SCHEMA_VERSION=1
> CONTRACT_HASH=cf2243febe2d1b924b4ca2c179abee9a341d703ed9945ba1ae579eeb2daf9e90
> 日期：2026-10-31
> 状态：DRAFT；冻结后版本升为 1.0，写入 `DECISIONS.md`
> 目标：规定 M1–M6 的唯一通信方式，消除跨模块具体实现依赖。
> 原则：模块之间只认 contract/port，不认实现；组合根负责装配。

---

## 1. 冻结目标

冻结后：

```text
M1..M6 之间只允许 import contracts/*
不允许 import 其他模块的 service/implementation
唯一例外：composition.py（组合根）
```

禁止：

```python
from lit_agent_v2.domains.report.source import SourceService
from lit_agent_v2.evaluation.runner import EvalRunner
from lit_agent_v2.domains.report.workflow import ReportWorkflow
```

允许：

```python
from lit_agent_v2.contracts.source import SourcePort, SourceArtifact
from lit_agent_v2.contracts.report import ReportPort
```

---

## 2. 中立契约包

新增/迁移：

```text
src/lit_agent_v2/contracts/
  __init__.py
  version.py
  run.py          RunRequest / RunState / NodeSpec / NodeState / WorkflowDefinition
  llm.py          LLMClient / LLMUsage / PromptRef
  source.py       SourceRequest / SourceArtifact / PaperRef / SourcePort
  evidence.py     EvidenceArtifact / Claim / Quote / EvidencePort
  map.py          MapArtifact / Direction / MapPort
  report.py       ReportPlan / EvidencePack / SectionArtifact / ReportDraft /
                  VerifiedReport / ReportPort / WriterPort / ReportRepository
  evaluation.py   MetricSpec / ScoreCard / EvaluationPort / JudgePort
  storage.py      Repository 接口与表所有权
  events.py       EventEnvelope / EventType
  errors.py       ErrorCode / ModuleError
```

原有：

```text
src/lit_agent_v2/contracts.py
src/lit_agent_v2/domains/report/contracts.py
```

在冻结迁移完成后删除，所有引用改到 `contracts/`。

### 版本

```python
CONTRACT_VERSION = "1.0"
```

每个 artifact 加：

```json
{"schema_version": 1}
```

冻结后：

- 加字段：允许，默认值必须有；
- 删/改字段：升 major；
- 错误码删除：禁止；
- port 方法签名变更：升 major；
- 必须同步 contract test + `DECISIONS.md`。

---

## 3. 模块职责边界

```text
M1 Engine        orchestration + kernel + state + storage interfaces
M2 Source        retrieval/ingest/metadata/fulltext
M3 Evidence      cards/claims/quotes
M4 Report        plan/map/write/assemble/persist
M5 Evaluation    metrics/scorecard/judge/dataset
M6 Interface     API/SSE/CLI/UI/Chat facade
```

### 唯一通信图

```text
                contracts/*
                    ▲
                    │
 M2 ── M3 ── M4 ── M5
  ▲     ▲     ▲     ▲
  └─────┴─────┴─────┘
        ports

 M1 ── contracts only
 M6 ── contracts + application ports
 composition.py ── all concrete implementations
```

规则：

- `M2` 不 import M3/M4/M5/M6；
- `M3` 不 import M4/M5/M6；
- `M4` 不 import M5/M6；
- `M5` 不 import M6；
- `M6` 不 import 具体 domain service，只 import application port；
- `M1` 不 import 任何 domain；
- `composition.py` 是唯一允许 import 所有模块的地方。

---

## 4. Ports

Ports 定义在 `contracts/`，由调用方依赖，不由实现方拥有。

### 4.1 M1

```python
class RunPort(Protocol):
    def prepare(self, request: RunRequest) -> str: ...
    def run(self, run_id: str, workflow: WorkflowDefinition, handlers: HandlerMap) -> RunResult: ...
    def pause(self, run_id: str) -> None: ...
    def resume(self, run_id: str) -> RunResult: ...
    def abort(self, run_id: str) -> None: ...

class ArtifactPort(Protocol):
    def put(self, payload: dict) -> str: ...
    def get(self, sha: str) -> dict: ...

class EventPort(Protocol):
    def emit(self, event: EventEnvelope) -> None: ...

class LLMClient(Protocol):
    def chat_json(self, messages, *, model, prompt_version, max_tokens, temperature) -> tuple[dict, LLMUsage]: ...
```

M1 不定义领域 port。

### 4.2 M2

```python
class SourcePort(Protocol):
    def fetch(self, request: SourceRequest) -> SourceArtifact: ...

class FulltextPort(Protocol):
    def enrich(self, paper: PaperRef) -> FulltextResult: ...
```

### 4.3 M3

```python
class EvidencePort(Protocol):
    def build(self, source: SourceArtifact, options: EvidenceOptions) -> EvidenceArtifact: ...
```

### 4.4 M4

```python
class MapPort(Protocol):
    def build(self, evidence: EvidenceArtifact) -> MapArtifact: ...

class DirectionWriterPort(Protocol):
    def write(self, pack: EvidencePack) -> SectionArtifact: ...

class ReportAssemblerPort(Protocol):
    def assemble(self, plan: ReportPlan, sections: list[SectionArtifact]) -> ReportDraft: ...

class ReportRepositoryPort(Protocol):
    def save(self, run_id: str, draft: ReportDraft) -> str: ...
```

### 4.5 M5

```python
class EvaluationPort(Protocol):
    def evaluate(self, report: VerifiedReport) -> ScoreCard: ...

class JudgePort(Protocol):
    def score(self, section: SectionArtifact, rubric: Rubric) -> JudgeResult: ...

class DatasetPort(Protocol):
    def load(self, name: str) -> EvalDataset: ...
```

### 4.6 M6

```python
class ReportApplicationPort(Protocol):
    def create(self, request: RunRequest) -> str: ...
    def status(self, run_id: str) -> RunStatus: ...
    def report(self, run_id: str) -> ReportView: ...
    def events(self, run_id: str, last_id: int = 0) -> Iterator[EventEnvelope]: ...

class ChatApplicationPort(Protocol):
    ...
```

---

## 5. Artifact 契约

### SourceArtifact

```json
{
  "schema_version": 1,
  "topic_id": "...",
  "query": "...",
  "papers": [{
    "paper_id": "...",
    "title": "...",
    "abstract": "...",
    "authors": ["..."],
    "venue": "...",
    "year": 2025,
    "url": "...",
    "pdf_url": "...",
    "html_url": "...",
    "source": "openalex"
  }],
  "readiness": {"requested": 100, "retrieved": 135, "relevant": 100},
  "provenance": {"strategy": "openalex", "retrieved_at": "..."}
}
```

### EvidenceArtifact

```json
{
  "schema_version": 1,
  "papers": [{
    "paper_id": "...",
    "title": "...",
    "level": "L1|L2",
    "fulltext_available": true,
    "fulltext_source": "pdf|html|abstract",
    "quote_windows": [{"text": "...", "section": "...", "page": 1}],
    "claims": [{
      "claim_id": "...",
      "text": "...",
      "quote": "...",
      "claim_type": "finding|method|dataset|limitation|background",
      "confidence": 0.8
    }]
  }],
  "coverage": {"papers": 100, "with_claims": 84, "fulltext": 30},
  "stats": {"quote_checks": 150, "quote_ok": 150, "claims": 150}
}
```

### MapArtifact

```json
{
  "schema_version": 1,
  "papers": 100,
  "directions": [{
    "direction_id": "D1",
    "name": "...",
    "paper_ids": ["..."],
    "claim_ids": ["..."],
    "coherence": 0.4,
    "outliers": []
  }],
  "min_size": 3,
  "outlier_rate": 0.0,
  "count_quality": "complete|deficit"
}
```

### ReportPlan / EvidencePack / SectionArtifact

见 `docs/modules/m4-report/M4-P02-modular-llm-writer.md`。

### VerifiedReport

```json
{
  "schema_version": 1,
  "report_id": "...",
  "state": "complete|degraded|failed",
  "sections": [],
  "claims": [],
  "content_sha": "...",
  "verdicts": [],
  "scorecard": {}
}
```

### ScoreCard

见 `docs/modules/m5-evaluation/M5-P01-scorecards-and-judge.md`。

---

## 6. 组合根

新增：

```text
src/lit_agent_v2/composition.py
```

唯一职责：

```python
def build_report_application(...) -> ReportApplicationPort:
    db = Database(...)
    artifacts = ArtifactStore(...)
    source = SourceService(...)
    evidence = EvidenceService(...)
    mapper = MapService(...)
    writer = LLMReportWriter(...)
    store = ReportRepository(db)
    workflow = ReportWorkflow(
        source=source,
        evidence=evidence,
        mapper=mapper,
        writer=writer,
        store=store,
    )
    return ReportApplication(workflow, ...)
```

规则：

- composition 可以 import M1–M6；
- M1–M6 不允许 import composition；
- composition 不写业务逻辑；
- composition 只做构造/注入；
- 测试可使用 fake 实现替换。

---

## 7. 数据库所有权

一个 SQLite 文件，逻辑表按模块归属：

| 表 | Owner | 访问方式 |
|---|---|---|
| `runs` / `run_nodes` / `run_artifacts` / `run_events` | M1 | M1 Repository |
| `reports` / `report_sections` / `claims` / `citations` | M4 | `ReportRepositoryPort` |
| `metric_points` / `run_spans` / `experiments` | M5 | `MetricRepositoryPort` |
| `chat_sessions` / `chat_messages` | M6 | `ChatRepositoryPort` |

规则：

- 模块只能写自己的表；
- 读其他模块数据必须通过 port，不直接 SQL；
- schema/migration 集中管理，变更需 owner review；
- 禁止跨模块事务写入。

当前违反：

- `M4/persist.py` 直接写 reports/claims；
- `M5/metric_store.py` 直接写 metric_points；
- `M6/api/app.py` 直接创建 Database / ReportWorkflow。

冻结后逐步改为 repository。

---

## 8. 错误契约

```python
@dataclass
class ModuleError(Exception):
    code: str
    message: str
    module: str
    retryable: bool
    details: dict
```

错误码见 `docs/ERRORS.md`。

规则：

- port 失败抛 `ModuleError`；
- 不抛裸 `RuntimeError` 跨模块；
- 不把内部异常类名暴露给 API；
- retryable 由 code 决定。

---

## 9. 事件契约

```json
{
  "schema_version": 1,
  "event_id": "...",
  "run_id": "...",
  "seq": 1,
  "ts": "...",
  "type": "node.finished",
  "module": "M4",
  "node_id": "write",
  "severity": "info",
  "payload": {}
}
```

规则：

- 事件由 M1 EventPort 写入；
- 模块通过 EventPort 发事件，不直接写 DB；
- `module` 必填；
- SSE 只读 M1 events；
- payload 不放大文本/密钥。

---

## 10. 指标契约

```python
@dataclass
class MetricPoint:
    metric_id: str
    module: str
    value: float | None
    numerator: float | None
    denominator: float | None
    sample_size: int
    run_id: str
    node_id: str | None
    config_hash: str
    prompt_version: str | None
```

规则：

- 指标由所属模块产生；
- M5 只读/评分，不替模块造假；
- M5 可定义公式，但不能修改源指标；
- 每个指标必须有 module。

---

## 11. 当前违反清单

| 违反 | 位置 | 目标 |
|---|---|---|
| M4 new M2/M3 concrete | `domains/report/workflow.py` | 注入 ports |
| M4 直接写 DB | `domains/report/persist.py` | `ReportRepositoryPort` |
| M5 new M4 workflow | `evaluation/runner.py` | 注入 `report_run` port |
| M6 new M4/M2 | `api/app.py` | 注入 `ReportApplicationPort` |
| M1 schema 包含所有表 | `storage/db.py` | 逻辑归属 + repository |
| contracts 分散 | `contracts.py` + `domains/report/contracts.py` | `contracts/` 包 |
| 错误裸抛 | 多个模块 | `ModuleError` |
| 事件无 module | `workflow/events.py` | EventEnvelope |

---

## 12. 迁移顺序

```text
C0 冻结本文件 v1.0
C1 建 contracts/ 包，迁移 dataclass
C2 定义 ports，不改实现
C3 建 composition.py
C4 M4 ReportWorkflow 依赖注入
C5 M4 ReportRepository
C6 M5 EvalRunner 注入
C7 M6 API 注入 application
C8 contract tests + import guard
C9 删除旧 contracts.py / domains/report/contracts.py
```

每一步可独立测试；C0 前不改业务代码。

---

## 13. 冻结检查表

- [x] 6 个模块的 port 签名确定；
- [x] artifact schema 确定；
- [x] 错误码确定；
- [x] 事件字段确定；
- [x] DB 表 owner 确定；
- [x] composition 唯一 import 例外；
- [x] contract tests；
- [x] import guard；
- [x] 旧 contract 删除计划；
- [x] `DECISIONS.md` 记录；
- [x] 版本 `CONTRACT_VERSION=1.0`。

冻结后：

```text
修改 port/artifact = major 变更
新增字段 = minor
新增错误码 = minor
删除 = 禁止，需新 major
```

---

## 14. 与 M1-P01 的关系

M1-P01 必须在本文件冻结后进行，且只能：

- 改 M1；
- 冻结 `LLMClient/LLMUsage/ToolSpec/KernelCheckpoint/NodeHandler`；
- 不 import M2–M6；
- 不改 ReportWorkflow。

C1–C4 已完成；M4-P02 只允许通过 ports 接 writer/verifier/scorer。

---

## 15. 当前状态

```text
版本：1.2 FROZEN
冻结：2026-10-31
CONTRACT_VERSION：1.2
SCHEMA_VERSION：1
M1-P01：可开始
C1–C9：完成
```


---

## 16. 实施进度（2026-10-31）

| 步 | 状态 | 说明 |
|---|---|---|
| C0 冻结 | ✅ | 2026-10-31；hash 已记录 |
| C1 contracts/ 包 | ✅ | `contracts/report.py`；`domains/report/contracts.py` 已删除 |
| C2 ports | ✅ | `contracts/ports.py` |
| C3 composition | ✅ | `src/lit_agent_v2/composition.py` |
| C4 ReportWorkflow 注入 | ✅ | 只依赖 ports；不再 import M2/M3 实现 |
| C5 ReportRepository | ✅ | `ReportStore` 实现 `ReportStorePort` / `ReportReaderPort` |
| C6 EvalRunner 注入 | ✅ | `EvalRunner(run_case)`；`build_eval_runner` 在 composition |
| C7 API application | ✅ | API 通过 composition 构建 workflow/chat/reader |
| C8 contract tests | ✅ | `test_contracts.py` + `test_boundaries.py` |
| C9 删除旧 contracts | ✅ | `domains/report/contracts.py` 已删除 |

### 已解决的耦合

- M4 `ReportWorkflow` 不再 new `SourceService/EvidenceService/MapService/WriteService`；
- M5 `EvalRunner` 不再 new `ReportWorkflow`；
- M6 API 不再 import `ReportWorkflow/LocalCorpus`；
- M4 通过 `ReportStorePort` 落库；
- M4 section 事件通过 `EventPort`；
- M4 metrics 通过 `MetricPort`。

### 仍未统一

- `storage/db.py` 是共享物理 schema；逻辑 owner 已在本文定义；
- API/DB 错误仍部分使用 HTTPException/RuntimeError，未全部改 `ModuleError`；
- `MetricStore` / `ChatStore` 仍直接写各自表（符合 owner，但不是 repository port）；
- C0 已冻结；以下为冻结后的实现一致性工作，不是接口变更。

### 当前门禁

```text
pytest tests/v2   53 passed
ruff              clean
```
