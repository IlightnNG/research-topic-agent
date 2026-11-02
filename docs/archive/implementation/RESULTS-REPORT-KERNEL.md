# RESULTS · Kernel-only Report Feasibility

> 日期：2026-11-01
> 目的：不使用 ReportWorkflow，只用一个 Node + 当前 Kernel + Tools 生成报告
> 结论：可行，但对提示词、工具数量和 token budget 很敏感

---

## 1. 实验设置

语料：

```text
D:\lit-agent-store\p41-report-experiment
3 papers
abstract-only
```

工具：

```text
corpus.papers
```

Node：

```text
id: report.generate
max_steps: 5
max_tokens: 12000
max_usd: 0.30
verifier: schema + claim + citation
```

LLM：

```text
deepseek-flash
```

---

## 2. 失败尝试

### 尝试 A：复杂流程

提示词要求：

```text
corpus.stats
corpus.papers
claims.extract
quote.check
report.plan
report.assemble
→ final
```

结果：

```text
stop_reason: max_steps
steps: 18
tool calls: 31
final: 未产生
```

现象：

```text
反复调用 corpus.stats / corpus.papers
claims.extract 多轮重复
report.plan 重复
没有进入 final
```

结论：

> 一个 Node 内同时要求检索、claim 提取、planning、写作时，Agent 容易在工具循环里打转。

### 尝试 B：单工具但 4000 max_tokens

结果：

```text
stop_reason: failed
tool calls: 1
completion_tokens: 4697 / 5022
output: {}
```

结论：

> 长报告 JSON 被输出上限截断，解析失败。

### 尝试 C：单工具 + 12000 max_tokens

结果：

```text
stop_reason: final
steps: 2
tool calls: 1
prompt_tokens: 1954
completion_tokens: 6529
```

输出：

```text
title: ...
content_md: 168 words
claims: 6
citations: 18
unique citations: 6
```

CodeVerifier：

```text
schema: pass
claim: pass
citation: pass
```

Quote 检查：

```text
C1 P1 True
C2 P1 True
C3 P2 True
C4 P2 True
C5 P3 True
C6 P3 True
```

---

## 3. 输出质量分析

### 好的地方

```text
6 个 claim 全部来自 abstract
6 个 quote 全部原文命中
18 个引用覆盖 6 个 claim
结构包含 overview / per-paper / synthesis / index
没有编造 paper
```

### 不足

```text
只有 3 篇
没有使用 report.plan
没有使用 report.assemble
synthesis 很薄
paper index 只是 citation 映射
没有 fulltext
```

### 结论

```text
Kernel 可以独立完成小规模报告任务
但前提是：
  1. 提示词明确且短；
  2. 工具数量少；
  3. max_tokens 足够；
  4. 有 code verifier；
```

---

## 4. 对 Report Node 的含义

Report Node 和其他 Node **契约相同**：

```text
NodeSpec
goal
tools
inputs
output_schema
verifier
max_steps / max_usd / max_tokens
```

它的特殊之处不是架构，而是：

```text
1. goal 更长，包含 procedure；
2. output 更大；
3. 需要更多 token；
4. 需要更严格的 verifier；
5. 工具更多，容易循环；
6. 需要 report.plan / report.write_section 把程序性知识移出 prompt。
```

---

## 5. 后续建议

```text
4.1.6 report.generate
  → 只负责 orchestration
  → report.plan 产出 sections
  → report.write_section 产出每节
  → report.assemble
  → verifier
```

不要让 report Node 在一个 prompt 里同时做检索、claim、planning、写作。

---

## 6. 产物

```text
D:\lit-agent-store\p41-report-experiment-result4.json
```

实验脚本：

```text
D:\lit-agent-store\temp\report_exp4.py
```

这两个文件在 workspace 外，仅作为本次实验记录。
