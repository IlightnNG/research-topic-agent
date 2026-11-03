# Testing

> 版本：1.1（2026-11-02）
> 范围：v2 only。旧 tests 已移出仓库。
> 目标：每个模块 phase 都有可执行验收，不靠“看起来跑通”。

> 架构 2.0 备注：文中旧 M1–M6 为历史模块 ID；新平台模块为 W/K/T/V/S/I，领域工具包为 R/E。

---

## 1. 测试层级

```text
L1 单元测试       纯函数/公式/解析
L2 契约测试       artifact schema / API schema
L3 模块测试       fixture + metric gate
L4 集成测试       RunShell + 多个模块
L5 真实集成       OpenAlex/PDF/LLM/100 篇
L6 评估测试       gold / judge / baseline
```

---

## 2. 命令

```powershell
. .\scripts\env.ps1
uv run pytest -q tests/v2
uv run ruff check .
```

后续增加：

```powershell
uv run pytest -q -m unit
uv run pytest -q -m contract
uv run pytest -q -m stage
uv run pytest -q -m integration
uv run pytest -q -m live
```

---

## 3. Fixture

```text
tests/v2/fixtures/
  source/
    papers-20.jsonl
    papers-100.jsonl
  evidence/
    claims-valid.json
    claims-author-list.json
    claims-truncated.json
  map/
    directions-5.json
    directions-collapsed.json
  report/
    report-valid.json
    report-count-mismatch.json
  eval/
    dataset-20.json
```

规则：

- fixture 必须可读、稳定；
- 真实数据另放 `D:\lit-agent-store\`；
- 不把 100 篇全文提交到 repo；
- fixture 变更要过 contract test。

---

## 4. 模块测试

| 模块 | 必测 |
|---|---|
| M1 | state/resume/pause/artifact/seq/kernel |
| M2 | OpenAlex/PDF/空结果/429/去重/metadata |
| M3 | 作者列表/截断 quote/claim 类型/purity |
| M4 | 计数一致/方向质量/index/字数 gate |
| M5 | 公式/NULL/数据集 freeze/评分/调参 |
| M6 | API/SSE replay/chat session/错误格式 |

---

## 5. Live 测试

```text
L5 不是 CI 默认；
失败不阻塞普通提交；
失败必须报告，不允许用 fake 代替结论。
```

Live 必测：

- OpenAlex 20 篇；
- PDF 至少 3 篇；
- 100 篇报告；
- LLM audit。

---

## 6. 验收门禁

Phase 完成必须：

```text
1. 单元测试；
2. 契约测试；
3. 模块 fixture gate；
4. 一个集成测试；
5. 无 legacy import；
6. 指标落库；
7. 失败路径测试。
```

没有失败路径测试，不算完成。

---

## 7. 真实 vs fake

必须标注：

```text
fake: 测试替身
live: 真实网络/模型/PDF
```

禁止：

- 用 fake 结果证明报告质量；
- 用旧测试证明新架构；
- 用“pytest 全绿”替代 live audit。

---

## 8. 当前

```text
tests/v2     128 passed
ruff         clean
```

Kernel 直接测试：

```text
tests/v2/test_tool_runtime.py
tests/v2/test_general_tools.py
tests/v2/test_agent_kernel.py
```

注意：当前 kernel 测试使用 ScriptedLLM，只验证控制流，不证明真实 LLM 质量。

真实联调：

- OpenAlex 135 篇；
- 100 篇报告；
- 5 篇全文；
- LLM audit：reject。

详见 `docs/archive/README.md` 的历史记录。


---

---

## Kernel 成熟度测试（Phase 4.2）

### L0–L3

```text
L0 Skeleton     固定 fake LLM
L1 Functional   多工具 / plan / memory / context / repair
L2 Hardened     并行 / checkpoint / 取消 / 错误 / 日志
L3 Benchmarked  真实 LLM 多任务 / 性能 / 质量门禁
```

Phase 4.2 进入 Workflow 前必须达到 L3。

### 必须覆盖

```text
tool timeout / exception / schema
unknown tool / policy deny
invalid LLM JSON
repeated tool call
max_steps / budget
context overflow / compaction
checkpoint corrupt / resume
cancel mid-tool
model 429 / timeout
parallel-safe / exclusive
NodeKernelAdapter smoke
```

### 真实 LLM Benchmark

```text
30+ tasks
workspace analysis
multi-file extraction
test failure repair
retrieval + citation
long task + compaction
tool selection
cancel / resume
```

指标：

```text
task_success_rate
schema_pass_rate
steps
tool_calls
tool_error_rate
repair_rate
prompt/completion tokens
cost
latency p50/p95
compaction ratio
resume success
```

L3 gate 已通过：简单 30/30，复杂 12/14，audit 13/14，soak 8/8。

详细要求见 [`KERNEL-MATURITY.md`](KERNEL-MATURITY.md)。

## 架构 2.0 测试层级

```text
W  Workflow：Node 链、optional、skip、resume
K  Kernel：goal/tools、budget、checkpoint
T  Tools：schema、idempotency、timeout
V  Verify：code fail、audit fail、combined verdict
R  Research：source/evidence/report tools
E  Evaluation：scorecard/judge
I  Interface：API/UI
```

Demo gate：

```text
100 papers
>=30 fulltext 或 abstract-only
overview + paper_analysis + synthesis + index
citation coverage = 1
code verifier pass
```
