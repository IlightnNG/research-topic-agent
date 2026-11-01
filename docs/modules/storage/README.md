# S · Storage

> 模块：Storage
> 版本：2.0（2026-11-01）
> 状态：target；现有 SQLite/Artifact 可复用
> 目标：持久化运行、artifact、事件、指标、报告。

---

## 1. 职责

```text
runs
run_nodes
run_artifacts
run_events
metric_points
reports / sections / claims / citations
artifact store
repositories
```

## 2. 不负责

```text
业务判断
LLM
Workflow 拓扑
```

## 3. 契约

```python
RunRepository
NodeRepository
ArtifactRepository
EventRepository
ReportRepository
MetricRepository
```

## 4. 目标文件

```text
storage/db.py
storage/artifacts.py
storage/repositories.py
storage/report_repository.py
```

## 5. 规则

- 表 owner 明确；
- 模块不直接写其他模块表；
- artifact 内容寻址；
- 事件 seq 单调；
- report repository 不暴露 SQL 给 Interface。

## 6. 验收

```text
migrate
artifact roundtrip
node commit/resume
report save/read
```

## 7. Phase docs

```text
S-P01-repositories.md
S-P02-report-store.md
```
