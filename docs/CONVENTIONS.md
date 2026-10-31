# Conventions

> 版本：1.0（2026-10-31）
> 适用：模块、phase、commit、TODO、错误、日志、状态文档。
> 所有新文档必须遵守；旧文档已移出仓库。

---

## 1. 模块 ID

固定 6 个：

```text
M1 Engine
M2 Source
M3 Evidence
M4 Report
M5 Evaluation
M6 Interface
```

文件夹：

```text
docs/modules/m1-engine/
docs/modules/m2-source/
docs/modules/m3-evidence/
docs/modules/m4-report/
docs/modules/m5-evaluation/
docs/modules/m6-interface/
```

---

## 2. Phase 命名

phase 文档直接放在模块文件夹：

```text
docs/modules/m3-evidence/M3-P01-claim-types.md
```

正则：

```regex
^M[1-6]-P\d{2}-[a-z0-9-]+\.md$
```

规则：

- 一个 phase 只改一个模块；
- `P01` 只增不改；
- slug 小写、短横线、≤5 词；
- 不允许 `phase3.6.md` 这类跨模块命名。

phase 文档必须包含：

```text
1. 目标
2. 边界（改什么/不改什么）
3. 接口/契约
4. 指标与 gate
5. 测试
6. 验收
7. 回滚
8. commit
```

---

## 3. Commit 标准

每个 phase 收尾只生成 **一句话英文 commit**：

```text
<type>(<module>-P<nn>): <summary>
```

示例：

```text
feat(M3-P01): add claim type validation and author-list rejection
fix(M4-P02): enforce claim-count reconciliation before publish
refactor(M1-P03): isolate checkpoint writer from workflow runner
test(M5-P01): add direction f1 fixture gate
docs(M2-P02): define openalex metadata contract
chore(M6-P01): remove legacy route scaffold
```

规则：

- 一行；
- 英文；
- 祈使句；
- ≤72 字符；
- 句末不加句号；
- type 只能是：
  ```text
  feat | fix | refactor | test | docs | chore
  ```
- 必须带模块和 phase；
- 一个 commit 只对应一个 phase；
- 不写 “update”, “improve”, “various fixes” 这类空话。

---

## 4. 模块 phase 状态

每个 phase 只能是：

```text
planned
in-progress
blocked
done
```

phase 完成定义：

```text
1. 只改本模块；
2. 契约测试通过；
3. 指标 gate 通过；
4. 单测 + 一个集成测试；
5. docs/STATUS/TODO 更新；
6. 无 legacy import；
7. 生成一句话 commit。
```

---

## 5. TODO 标准

ID：

```text
TODO-001
```

字段：

```text
ID | Module | Phase | Priority | Status | Title | Evidence | Acceptance | Links
```

优先级：

```text
P0 阻断正确性/报告不可用
P1 核心质量
P2 产品/体验
P3 长期
```

状态：

```text
open | in-progress | blocked | done
```

规则：

- 一个 TODO 只属于一个模块；
- 必须写 evidence 和 acceptance；
- 完成后保留，不删除；
- 不新建重复 TODO，先搜 ID。

---

## 6. 文档头部

每个文档第一段必须是：

```text
> 版本：
> 更新：
> 范围：
```

模块 README 额外写：

```text
> 模块 ID：
> 代码：
> 目标：
```

---

## 7. 代码边界

- `lit_agent_v2` 不 import `lit_agent`；
- 模块之间只通过 contracts/artifact 交互；
- 不允许跨模块直接访问内部函数；
- 不允许模块直接改其他模块的 DB 表；
- 共享契约改动必须同时更新 producer/consumer/contract test。

---

## 8. 文件命名

```text
docs/ARCHITECTURE.md
docs/CONVENTIONS.md
docs/ERRORS.md
docs/LOGGING.md
docs/TESTING.md
docs/STATUS.md
docs/TODO.md
docs/modules/README.md
docs/modules/mX-name/README.md
docs/modules/mX-name/MX-Pnn-slug.md
```

禁止：

```text
phase3.6.md
new.md
old.md
final.md
misc.md
```
