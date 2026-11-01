# RESULTS · S6 Report Node

> 日期：2026-11-01
> 范围：4.1.6 report.generate
> 性质：1 Node Workflow + fake E2E + live LLM mini report

---

## 1. 实现

```text
tools/packs/report.py
  report.plan
  report.write_section
  report.check_section
  report.assemble
  report.persist

workflow/node/definition.py
  build_report_workflow        # full chain
  build_report_demo_workflow   # one-node local-corpus demo
```

`report.write_section`：

```text
section + claims + LLM
  → body with [C#]
  → section artifact
  → problems if empty/unknown citation
```

`report.persist`：

```text
root + title + content_md + claims
  → report.md
  → report.json
  → path + word_count
```

---

## 2. Fake E2E

`tests/v2/test_report_node_e2e.py`：

```text
corpus.papers
claims.extract x2
report.plan
report.write_section x4
report.assemble
report.persist
final
```

结果：

```text
committed
report.json exists
report.md exists
verifier pass
```

---

## 3. Live LLM run

语料：

```text
3 papers, abstract-only
```

Workflow：

```text
report-demo / report.generate
```

真实调用：

```text
17 steps
```

工具序列：

```text
1  corpus.papers
2  claims.extract x3
3  report.plan
4  report.write_section x6
5  report.write_section x2
6  report.assemble
7  corpus.papers
8  report.persist
9  report.persist
```

结果：

```text
stop_reason: final
words: 301
claims: 5
path: D:\lit-agent-store\p41-report-experiment\report.json
verdict: accept
code: schema, claim, citation, word_limit, file_exists all pass
```

输出结构：

```text
Paper Analyses
Cross-Paper Synthesis
Gap / limitation
```

---

## 4. 分析

### 成功

```text
一个普通 Node 完成了报告生成
没有 ReportWorkflow
没有 deterministic writer
Kernel 负责 tool loop
Verifier 负责输出验收
```

### 问题

```text
17 steps 偏多
report.write_section 被调用 8 次（重复 section）
corpus.papers 被调用 2 次
report.persist 被调用 2 次
没有调用 report.check_section
```

原因：

```text
工具本身无状态；
Agent 看不到“哪些 section 已写”；
prompt 没有强约束“每个 section 一次”；
没有 section registry / idempotency。
```

### 结论

Report Node 可以完成报告，但当前瓶颈不是 Kernel，
而是 **report tools 缺少状态和幂等语义**。

---

## 5. Report Node 的特殊性

它和其他 Node 完全平等：

```text
NodeSpec
Kernel
ToolRegistry
Verifier
```

特殊的是：

```text
1. tools 更多；
2. 输出更大；
3. 需要 max_tokens=12000；
4. 更容易重复调用；
5. 需要 report.check_section；
6. 需要 section state。
```

因此后续优化重点：

```text
report.write_section 记录 section_id，重复调用返回已写内容
report.plan 输出 section registry
report.check_section 强制逐节验收
report.assemble 只接受完整 section set
```

而不是：

```text
给 report 做特殊 Node 类型
给 report 写专属 Workflow
```
