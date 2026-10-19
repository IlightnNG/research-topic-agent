# ADR 索引（Architecture Decision Records）

> 用途：记录**冻结契约与关键设计**的变更决策，保证"为什么改"可追溯（详见 `../implementation-guide.md` §15.4 与附录 C）
> 命名：`NNNN-<kebab-title>.md`（四位序号，如 `0001-switch-graph-store.md`）

## 何时必须写 ADR

| 触发 | 示例 |
|---|---|
| 冻结契约变更 | 表结构、事件 schema、API 路径/字段、Pydantic 模型字段 |
| 依赖变更 | 新增未列入依赖基线的库（如 Redis/Celery） |
| 选型变更 | 换图库/向量库/网关/编排框架 |
| 提示词或阈值版本变更（影响可复现性） | 提示词模板大改、守卫阈值重新标定 |

## 模板

```
# ADR NNNN: <title>
Status: proposed | accepted | rejected
Context: 现状与动机
Decision: 变更内容（接口/表/事件/schema）
Impact: 受影响模块与测试
Migration: 迁移步骤（含数据）
Verification: 回归与验收命令
```

## 当前记录

| ADR | 标题 | 状态 | 触发来源 |
|---|---|---|---|
| [0001](0001-paper-merged-ids.md) | `Paper.merged_ids` 与 `paper_merges` 表（去重合并关系入契约） | accepted | S1b 重复率 19.3–19.8% + S5 契约缺口 |
| [0002](0002-metric-event-contract.md) | 指标事件契约（`metric{kind}`）与"事件即真相源"的埋点义务 | accepted | S7 三次因埋点缺失算不出指标 + S6 日志≠事件 |
| [0003](0003-local-store-path-and-identity.md) | 本地存储的路径形态、生命周期与"库身份"校验 | accepted | S3 旧库残留/落盘时机/非 ASCII 路径 + S5 schema 漂移 |
| [0004](0004-vector-source-and-embedding-model.md) | 向量部署形态、嵌入模型与重嵌入流程（local + `bge-m3` 1024 维） | accepted | guide §2.6 只锁维度未锁来源；S3b 实测 local 无 ANN |
| [0005](0005-entity-tables-and-event-keys.md) | 论文实体表、事件序号分配与幂等键（24 张表 + seq/幂等总表） | accepted | guide §2.1 缺论文实体表；§2.2 未定 seq 与冲突策略 |

> Phase 0（Step 0–7）实测中共触发上述 3 项契约/部署变更；其余 Phase 0 结论属"实现与阈值标定"，
> 已写入 `design/` 与 `implementation/` 相应文档，无需 ADR（判据见上表"何时必须写 ADR"）。
>
> **Phase 1 增量**：0004/0005 为 Phase 1 Step 1.3 与 1.5 的前置决策（分别解锁"事件表与实体表"与"向量库"），
> 其落地步骤见 `../phase1-implementation-steps.md` §4 的 Step 1.3 / Step 1.5。
