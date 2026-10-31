# RESULTS · M4-P01

> Phase：M4-P01 Direction Quality + Count Reconciliation
> 日期：2026-10-31
> 状态：done（100 篇方向/计数通过；words degraded，M4-P02 修复）

## 门禁

```text
pytest tests/v2   53 passed（含 2 个 live LLM）
ruff              clean
contract freeze   v1.2 passed
```

## 已实现

### Direction quality

```text
- 5–8 directions
- min_size >= 3
- max_share <= 0.6
- small groups 不再合并成单一 Other
- count_quality = complete / deficit
```

### Direction names

- 过滤作者名；
- 过滤 venue；
- 过滤重复名；
- fallback `Topic N`。

### Count reconciliation

```text
overview claims = deep dive claims = matrix claims = ledger claims
```

- deep dive 不再只展示 6 条；
- ledger 只是索引，不再单独刷 coverage；
- `report.count_reconciliation` 进入指标。

### Paper Index

```text
| Paper | Title | Authors | Venue | Year | URL |
```

### Coverage

```text
report.claim_coverage
  = deep_dive displayed claims / claims
```

不再使用 ledger。

## 测试

```text
tests/v2/test_m4_report.py
  - 5–8 directions
  - max_share
  - 作者/venue 名过滤
  - 50 claims 计数一致
  - Paper Index metadata
  - collapsed direction → degraded
  - 所有 claim 出现在正文，不只是 ledger
```

## 真实 100 篇（OpenAlex metadata-only）

```text
directions   5
min size     3
max share    0.35
claims       178
words        10775
state        degraded
```

方向质量已通过；word count 仍过高，原因是 deterministic appendix 和所有 claim 全文重复。M4-P02 的 LLM writer 会压缩。

## 当前边界

- writer 仍是 deterministic；
- 100 篇真实报告未复跑；
- comparison 仍只有表格，没有 LLM 正文（M4-P02）；
- open questions 仍是模板（M4-P02）；
- 方向命名仍是词频，不是 LLM/embedding；
- 80% claim coverage 现在是 100%（因为不再截断），但正文可读性一般。

## Commit

```text
fix(M4-P01): enforce direction quality and claim-count reconciliation
```
