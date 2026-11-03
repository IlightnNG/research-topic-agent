# RESULTS · Phase 4.2 S10.1–S10.3

> Status：API 接入、逐 section 写入、CLI checkpoint/resume 已完成
> Date：2026-11-03
> Report：5 Node / real LLM / 100 papers

---

## 1. S10.1 API 接入

`PlatformRunService` 增加：

```text
LIT_V2_WORKFLOW=report-v2
```

默认工作流现在可以选择：

```text
report-v2
demo100      legacy
report-demo  legacy/single
```

API 分支：

```text
WorkflowRunner
  → KernelNodeAdapter
  → AgentKernel
  → 5 report Node
  → DbNodeStore
  → SQLite run_events / run_nodes
```

真实 API 运行：

```text
run_id          run-a7728c288180
state           succeeded
nodes           source.collect / evidence.extract / report.plan /
                report.write / report.audit_finalize all committed
report           100 papers
fulltext         35
claims           186
sections         23
word_count       5135
state            complete
citation_coverage 1.0
```

报告：

```text
D:\lit-agent-store\v2-api-v2-100\run-a7728c288180\report.md
D:\lit-agent-store\v2-api-v2-100\run-a7728c288180\report.json
```

---

## 2. S10.2 逐 section 写入

新增工具：

```text
report.write_section_v2
report.check_section_v2
report.assemble_v2
```

section 文件：

```text
out_dir/sections/{section_id}.json
```

内容：

```text
section_id
kind
title
body
claim_ids
attempts
ok
problems
fallback
```

实现行为：

```text
每个 section 单独写
失败最多重试 3 次
section 文件存在且 ok 时 resume 跳过
失败后使用 deterministic evidence fallback
paper_index 不要求 citation
最后 assemble 时任何 missing/failed section 都会失败
```

真实 CLI 运行：

```text
sections            23
word_count          5090
citation_coverage   1.0
```

---

## 3. S10.3 checkpoint / resume

新增：

```text
FileCheckpointStore(out_dir/checkpoints)
JsonNodeStore(out_dir/nodes)
```

CLI：

```bash
python -m lit_agent_v2.interface.cli report-v2 \
  --corpus ... --out ... --resume
```

验证：

```text
第一次运行：5 Node committed
第二次 --resume：
  5 个 Node 直接从 JsonNodeStore 读取
  没有重新调用 LLM
  输出同一份 report
```

API：

```text
KernelNodeAdapter(checkpoints=FileCheckpointStore(...))
WorkflowRunner(resume=True)
DbNodeStore committed output
```

---

## 4. Tests

```text
124 passed
ruff clean
```

新增覆盖：

```text
API workflow 选择 report-v2
per-section retry
JsonNodeStore commit/load
CLI resume
```

---

## 5. 当前边界

```text
S10.2 已完成 tool-level + Node-level per-section
  report.write 默认通过 section cursor 逐步调用

S10.3 CLI resume 已验证
  API resume 代码路径已接，但没有做真实中断测试

S10.4 尚未移除生产 DemoOrchestrator
S10.5 尚无完整 report quality gate
```

---

## 6. 下一步

```text
S10.4 移除生产 DemoOrchestrator
S10.5 report quality gate
S10.6 100 篇最终门禁
S10.7 cleanup
```
