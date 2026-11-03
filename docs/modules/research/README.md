# R · Research

> 模块：Research
> 版本：2.0（2026-11-01）
> 状态：target；旧 M2/M3/M4 服务将被工具化
> 目标：source / evidence / report 的领域工具包。
> 报告格式模板见 [`REPORT-TEMPLATE.md`](REPORT-TEMPLATE.md)。

---

## 1. 职责

```text
source.search
source.fetch_pdf
source.fetch_html
corpus.store
corpus.stats
corpus.dedupe

claims.extract
quote.check
claims.filter
evidence.stats

report.plan
report.write_section
report.check_section
report.assemble
```

## 2. 不负责

```text
Workflow
Kernel
最终 commit
API
另一个领域 service
```

## 3. 目标文件

```text
domains/research/artifacts.py
domains/research/prompts/
tools/packs/source.py
tools/packs/corpus.py
tools/packs/evidence.py
tools/packs/claims.py
tools/packs/report_plan.py
tools/packs/report.py
```

## 4. Report Node

当前一个：

```text
report.generate
```

工具：

```text
report.plan
report.write_section
report.check_section
report.assemble
```

章节由 `report.plan` 产物决定，不写死。

## 5. 规则

- 领域能力通过 Tool 暴露；
- 不直接调用其他领域 service；
- quote 必须由代码检查；
- `report.plan` 不能生成未知 section kind；
- 100 篇 demo 不要求 classification。

## 6. 验收

```text
100 篇 source
100 篇 claims
report sections
quote exact
report plan optional sections
```

## 7. 当前实现

```text
tools/packs/report.py
  report.plan
  report.write_section
  report.check_section
  report.assemble
  report.persist

workflow/node/definition.py
  build_report_workflow
  build_report_demo_workflow
```

状态：4.1.6 done；report node 已可完成 3 篇 mini report。

## 8. Phase docs

```text
R-P01-source-tools.md
R-P02-evidence-tools.md
R-P03-report-generate-node.md
```
