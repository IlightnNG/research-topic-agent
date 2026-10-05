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

（暂无。首次契约变更时在此追加，例如 `0001-*.md`。）
