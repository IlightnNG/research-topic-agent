# RESULTS · Phase 4.2 S10.4–S10.7

> Status：S10.4 / S10.5 / S10.7 done；S10.2b Node-level loop done
> Date：2026-11-03
> Report：100 papers / 35 fulltext / 186 claims / 23 sections

---

## 1. S10.4 移除生产 DemoOrchestrator

改动：

```text
interface/runs.py 删除 DemoOrchestrator import
删除 full-chain 的 DemoOrchestrator 分支
report-v2 仍是默认生产路径
demo100 仅保留显式 legacy
```

Guard：

```text
tests/v2/test_report_v2.py
  test_no_demo_orchestrator_in_interface
```

结果：

```text
src/lit_agent_v2/interface/ 中 DemoOrchestrator = 0
```

---

## 2. S10.5 Report Quality Gate

新增：

```text
report.quality.check
check_report_quality()
finalize_report(strict_quality=True)
```

门禁：

```text
papers >= 100
fulltext >= 35，或 state=degraded
claims >= 100
sections >= 10
word_count 3500–8000
citation_coverage = 1.0
empty sections = 0
reference problem sections = 0
```

失败：

```text
E_REPORT_QUALITY
finalize Node 失败
不写 complete report
```

真实 100 篇结果：

```text
papers            100
fulltext          35
claims            186
sections          23
word_count        5248
citation_coverage 1.0
empty sections    0
reference problems 0
accepted          true
```

输出：

```text
D:\lit-agent-store\v2-report-v2-quality\report.json
D:\lit-agent-store\v2-report-v2-quality\report.md
```

边界：

```text
当前是 deterministic quality gate
LLM audit 未作为 hard gate
LLM audit 可以在后续作为 advisory 或第二阶段门禁
```

---

## 3. S10.7 Cleanup

```text
移除生产 DemoOrchestrator
保留 demo100 为显式 legacy
更新 TODO / STATUS / TESTING
新增 no-demo guard
更新阶段文档
```

测试：

```text
125 passed
ruff clean
```

---

## 4. 当前 S10 状态

```text
S10.0  5 Node CLI                 done
S10.1  API 接入                   done
S10.2  逐 section + retry         done（Node-level）
S10.3  checkpoint / resume        done（CLI 验证）
S10.4  移除生产 DemoOrchestrator  done
S10.5  report quality gate        done（deterministic）
S10.6  100 篇端到端               done（CLI + API）
S10.7  cleanup                    done
```

S10.2b Node-level loop 已完成；批量 `report.write_v2` 仅保留兼容。

---

## 5. Next

```text
S10.2b Node-level section loop（done）
S11 report optimization
S12 Chat
```
