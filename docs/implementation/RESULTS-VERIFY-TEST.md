# RESULTS · Verify Test

> 日期：2026-11-01
> 范围：CodeVerifier、AuditVerifier、Verifier、WorkflowRunner 集成
> 性质：fake LLM；无 live audit

---

## 1. 总门禁

```text
pytest tests/v2   131 passed
ruff              clean
```

新增：

```text
tests/v2/test_verify_dual.py
```

---

## 2. Code checks

已实现：

```text
schema
papers
dedupe
claim
quote
citation
count
word_limit
file_exists
directions
```

测试覆盖：

| 检查 | 通过 | 失败 |
|---|---|---|
| schema | object output | 非 object |
| papers | 唯一 paper_id | 重复 paper_id |
| dedupe | 唯一 title | 重复 title |
| claim | 非空、唯一 claim_id | 空/重复 |
| quote | 原文命中 | 空/找不到 |
| citation | 有 [C#] | 无引用 |
| count | 数量一致 | 数量不一致 |
| directions | 1–8 个 | 空/超过 8 |
| unknown | — | 拒绝未知 check |

---

## 3. Audit

规则：

```text
code fail → reject（audit 不能覆盖）
code pass + audit fail → reject/repair
code pass + audit accept → accept
audit 缺失但 required → reject
audit=None → code only
audit_required=False → audit 失败不阻塞
```

Audit 输入：

```text
Node goal
declared inputs
candidate output
```

不接收：

```text
producer trace
chain-of-thought
```

---

## 4. Integration

`Verifier` 已满足 `WorkflowRunner` 的 `VerifierPort`：

```text
code checks
→ audit
→ Verdict
→ commit / NodeFailed
```

测试：

```text
valid output → committed
audit repair → NodeFailed
```

---

## 5. 当前限制

```text
word_limit 固定 8000
citation 只检查 [C#] 形态和上界
quote 检查依赖 output.text
没有 repair loop
没有 live LLM audit 测试
没有 section 级验证
```

这些在 4.1.6 report node 中补。

---

## 6. 结论

双 Verifier 已可用：

```text
CodeVerifier + AuditVerifier
→ Verdict
→ WorkflowRunner
```

下一阶段：

```text
4.1.6 report.generate agent node
```
