# Baseline · Phase 4.1.0

> 日期：2026-11-01
> 目的：记录 Node Platform 迁移前基线
> 代码：迁移前；old ReportWorkflow 仍存在

---

## 1. 测试基线

```text
uv run pytest -q tests/v2   77 passed
uv run ruff check .         clean
```

包含：

```text
3 live LLM tests
M1–M6 legacy tests
```

---

## 2. 100 篇 deterministic 报告基线

语料：

```text
D:\lit-agent-store\v2-eval\gold\corpora\agents
100 papers
abstract-only
```

结果：

```text
papers        100
claims        174
directions    5
min size      7
max share     0.27
quality       complete
narrative     5230 words
state         degraded
fulltext      0/100
citation      1.0
uncited       0
duplicate     0
```

结构：

```text
overview
deep_dive D1..D5
comparison
gaps
method
paper_index
claim_ledger
```

结论：

```text
结构可用
fulltext 0/100 → state degraded
默认 writer = deterministic
```

---

## 3. 旧代码入口基线

当前仍存在的旧路径：

```text
ReportWorkflow
WriteService
domains/report/workflow.py
domains/report/write.py
contracts/ports.py
run_shell.py
```

迁移期间：

```text
旧路径暂时保留
新路径不得 import 旧路径
最终 4.1.9 删除
```

---

## 4. 迁移后必须保持

```text
100 papers 可跑
claims 有 quote
citation coverage = 1
API/UI 可读
```

允许变化：

```text
deterministic writer 删除
章节固定列表删除
classification 默认关闭
fulltext 不足时 abstract-only + degraded
```
