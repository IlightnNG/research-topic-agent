# RESULTS · M2-P01

> Phase：M2-P01 Metadata + Fulltext
> 日期：2026-10-31
> 状态：done（100 篇 live ratio 待复跑）

## 门禁

```text
pytest tests/v2   49 passed（含 2 个 live LLM）
ruff              clean
contract freeze   v1.2 passed
```

## 已实现

```text
contracts/report.py
  Paper.authors

domains/report/openalex.py
  authorships
  doi / landing page / pdf / html

domains/report/source.py
  title 缺失拒绝
  metadata.completeness
  metadata.authors_rate

domains/report/ingest.py
  authors 持久化
  PDF → HTML → abstract 回退
  fulltext 文件写入

domains/report/pdf.py
  PDF 文本
  HTML 文本
```

## 真实 OpenAlex 冒烟

```text
10 篇
authors    10/10
complete   10/10
fulltext    3/10（30%）
```

样本：

```text
W4416036673  76725 chars
W7106851738   1527 chars
W7161024840   5094 chars
```

## 测试

```text
tests/v2/test_m2_source.py
  metadata metrics
  empty title filter
  HTML fallback
  ingest fulltext
  HTML stripping
```

## 契约

```text
CONTRACT_VERSION 1.2
CONTRACT_HASH cf2243febe2d1b924b4ca2c179abee9a341d703ed9945ba1ae579eeb2daf9e90
```

## 当前边界

- 100 篇 fulltext ratio 未重新跑；
- OpenAlex 是第一优先源；arXiv/Semantic Scholar 未接；
- 扫描 PDF 无文本层仍降级 abstract；
- 没有独立的 fulltext failure metric；
- M2 不抽 claim。

## Commit

```text
feat(M2-P01): add paper metadata and fulltext fallback
```
