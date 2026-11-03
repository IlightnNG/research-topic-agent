# RESULTS · Phase 4.2 S10.2b

> Status：done
> Date：2026-11-03
> Mode：Node-level section loop

---

## 1. 实现

`report.write` 不再直接调用批量 `report.write_v2`，而是：

```text
report.section_status
  → report.write_next_section
  → report.write_next_section
  → ...
  → remaining = 0
  → report.assemble_v2
  → final
```

新增工具：

```text
report.section_status
report.write_next_section
```

`write_next_section` 是 repeatable tool：

```text
相同参数可以重复调用
不触发 Kernel no-progress
每次只写下一个未完成 section
```

Kernel 现在支持：

```text
ToolSpec.repeatable
```

Node policy 也改为使用 NodeSpec：

```text
max_steps
max_usd
max_tokens
timeout_s
```

`report.write` 预算：

```text
max_steps 30
max_usd 1.50
max_tokens 20000
```

---

## 2. 真实运行

100-paper local corpus：

```text
papers            100
fulltext          35
claims            186
sections          23
word_count        5479
state             complete
citation_coverage 1.0
```

section 文件：

```text
out_dir/sections/*.json
```

统计：

```text
sections          23
total attempts    29
fallback sections 2
```

说明：

```text
存在真实 section 重试
不是整篇重跑
```

输出：

```text
D:\lit-agent-store\v2-report-v2-node-loop\report.md
D:\lit-agent-store\v2-report-v2-node-loop\report.json
```

五个 Node 全部 committed。

---

## 3. Tests

新增：

```text
test_section_cursor_loop
```

覆盖：

```text
status
write_next_section
remaining/done
assemble
citation coverage
```

全量：

```text
126 passed
ruff clean
```

---

## 4. 状态

```text
S10.2  逐 section + retry   done
S10.2b Node-level loop      done
```

当前 Node-level loop 已是默认路径；批量 `report.write_v2` 仅保留为兼容/fallback。
