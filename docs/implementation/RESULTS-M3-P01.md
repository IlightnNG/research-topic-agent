# RESULTS · M3-P01

> Phase：M3-P01 Claim Quality
> 日期：2026-10-31
> 状态：done

## 门禁

```text
pytest tests/v2   46 passed（含 2 个 live LLM）
ruff              clean
contract freeze   v1.1 passed
```

## 已实现

```text
domains/report/claim_extractor.py
  classify_claim
  build_claim
  extract_deterministic
  LLMClaimExtractor

domains/report/evidence.py
  quote exact check
  type-aware claim counting
  research_claims / claim_purity
```

## 规则

- 5 类：
  ```text
  finding
  method
  dataset
  limitation
  background
  ```
- 拒绝：
  - 作者列表；
  - references / DOI / URL；
  - acknowledgements / funding；
  - copyright；
  - 截断句；
  - 缺少 claim verb；
  - 少于 8 words；
  - 非原文 quote。
- `background` 不作为 research claim；
- `claim_type` 写入 evidence artifact。

## 测试

```text
tests/v2/test_m3_claims.py
  - valid types
  - author list reject
  - references/ack/truncated reject
  - background reject
  - LLM non-verbatim filter
  - purity
  - live LLM extraction
```

## 契约

`Claim.claim_type` 为 additive minor：

```text
CONTRACT_VERSION 1.1
CONTRACT_HASH 8df591896a40b6efd65780191a9b94ad76f39316cdf06c96274574ab6b8f4f96
```

## 当前边界

- M4 仍使用 deterministic claim_extractor；
- 还没有把 M3 extractor 注入 LLM writer（M4-P02）；
- `claim.nonresearch_rate` 未单独落指标；
- truthfulness 仍依赖 quote gate。

## Commit

```text
feat(M3-P01): add typed claims and non-research rejection
```
