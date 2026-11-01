# C · Composition

> 模块：Composition
> 版本：2.0（2026-11-01）
> 状态：target
> 目标：唯一装配点。

---

## 1. 职责

```text
构建 ToolRegistry
构建 Kernel
构建 Verifier
构建 WorkflowDefinition
构建 Storage repositories
构建 Interface app
选择 FeatureProfile
```

## 2. 不负责

```text
业务逻辑
Node 内部流程
报告内容
验证规则实现
```

## 3. 目标文件

```text
composition.py
```

## 4. 规则

- 唯一允许 import 所有 concrete 模块；
- Workflow/Kernel/Interface 不 import Composition；
- 不写业务逻辑；
- 只做构造/注入；
- demo/full profile 在这里选择。

## 5. 验收

```text
demo profile 可构建
full profile 可构建
无循环 import
Interface 只拿到 use case
```

## 6. Phase docs

```text
C-P01-composition-profiles.md
```
