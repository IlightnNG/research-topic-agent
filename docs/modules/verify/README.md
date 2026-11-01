# V · Verification

> 模块：Verification
> 版本：2.0（2026-11-01）
> 状态：target
> 目标：决定 Node 输出能否 commit。

---

## 1. 职责

```text
CodeVerifier
AuditVerifier
Verdict
repair / reject
verification profile
```

## 2. 不负责

```text
生成内容
修复内容
Workflow 调度
工具执行
```

## 3. 双验证

```text
candidate
  → code checks
  → LLM audit
  → Verdict
```

Code：

```text
schema
paper_id / claim_id
quote exact
citation coverage
count reconciliation
word limit
file exists
budget
```

Audit：

```text
relevance
coverage
readability
synthesis
grounding
```

## 4. 目标文件

```text
verify/code.py
verify/audit.py
verify/verdict.py
```

## 5. 规则

- code hard fail 不能被 audit 覆盖；
- audit fail 可触发 repair；
- audit 不接收 producer 推理链；
- 所有 Node 默认 code + audit；
- Verdict 写入 artifact/event。

## 6. 验收

```text
code pass + audit pass → accept
code pass + audit fail → repair
code fail → reject
```

## 7. Phase docs

```text
V-P01-code-verifier.md
V-P02-audit-verifier.md
```
