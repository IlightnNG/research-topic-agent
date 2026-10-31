# RESULTS · M4-P02

> Phase：M4-P02 Modular LLM Writer
> 日期：2026-10-31
> 状态：done（20 篇 live complete；100 篇 live 待 M5 前复跑）

## 门禁

```text
pytest tests/v2   57 passed（含 3 个 live LLM）
ruff              clean
contract freeze   v1.2 passed
```

## 已实现

```text
domains/report/plan.py
  ReportPlan
  PlanSection
  EvidencePack
  build_plan / pack_for

domains/report/llm_writer.py
  LLMReportWriter
  per-direction LLM section
  structured JSON (common_ground / differences / open_questions)
  citation gate
  coverage gate
  duplicate gate
  retry
  deterministic fallback
  section streaming callback

domains/report/audit.py
  narrative words
  citation coverage
  uncited facts
  duplicate claim rate
```

## LLM 合约

Section 输出：

```json
{
  "common_ground": [{"text": "...", "refs": ["C1"]}],
  "differences": [{"text": "...", "refs": ["C2"]}],
  "open_questions": [{"text": "...", "refs": ["C3"]}]
}
```

代码负责：

- 校验 refs；
- 去重；
- 生成 `- text [C#]`；
- 补缺失 claim 到 Evidence notes；
- 保证每个 claim 只出现一次；
- 校验 coverage / uncited / duplicate；
- 失败重试；
- 仍失败使用 deterministic section，并标 degraded。

## live 20 篇

```text
state       complete
words       611（policy 480–1920）
claims      20
sections    overview + 3 deep_dive + comparison + gaps + method + index + ledger
audit       citation_coverage=1.0, uncited=0, duplicate=0
```

## 未完成

- 100 篇 live LLM writer 未复跑；
- overview/comparison 某些模型会回退 deterministic；
- LLM 调用成本/延迟未做预算；
- open questions 仍是 evidence-derived，不是深层研究空白；
- 尚无 LLM judge（M5）。

## Commit

```text
feat(M4-P02): add per-direction llm report writer
```
