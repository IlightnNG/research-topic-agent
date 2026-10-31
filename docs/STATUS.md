# STATUS

> 版本：1.0（2026-10-31）
> 用途：AI 长周期交接；每个 phase 收尾必须更新。
> 只写事实，不写计划口吻。

---

## 当前状态

```text
阶段：v2 prototype
最后测试：23 passed / ruff clean
真实联调：100 篇 OpenAlex，报告 degraded
LLM audit：reject
```

---

## 模块

| 模块 | 状态 | 当前 phase | 下一 phase |
|---|---|---|---|
| M1 Engine | prototype | — | M1-P01 |
| M2 Source | prototype | — | M2-P01 |
| M3 Evidence | prototype | — | M3-P01 |
| M4 Report | prototype | — | M4-P01 |
| M5 Evaluation | prototype | — | M5-P01 |
| M6 Interface | prototype | — | M6-P01 |

---

## 契约状态

```text
CONTRACTS.md  1.0 FROZEN；C1–C9 已落地
M4-P02 已无接口阻塞；可进入 M1-P01
```

## 当前阻塞

1. M3 claim 质量（作者列表/截断/purity）；
2. M4 计数不一致、方向塌缩、无 LLM writer；
3. M2 全文只有 5/100；
4. M5 无 100 篇 gold / judge；
5. M6 无生产 UI。

---

## 下一步

按模块顺序：

```text
M1-P01 Kernel ReAct + LLM client
M3-P01 claim 类型与作者列表过滤
M2-P01 metadata + 全文率
M4-P01 方向质量 + 计数一致
M4-P02 分方向 LLM writer
M5-P01 scorecard + judge
M6-P01 Report API + minimal UI
```

优先级见 `docs/TODO.md`。

---

## 最近变更

```text
2026-10-31  legacy code/docs 移出仓库
2026-10-31  v2 100 篇真实联调
2026-10-31  LLM audit reject
2026-10-31  模块文档/规范建立
```

---

## 交接规则

1. 先读 `docs/STATUS.md`；
2. 再读 `docs/modules/README.md`；
3. 只改当前模块；
4. phase 完成更新 STATUS/TODO；
5. 生成一句话 commit；
6. 不恢复旧代码。
