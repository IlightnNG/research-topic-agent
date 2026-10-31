# M2-P01 · Metadata + Fulltext

> 模块：M2 Source
> 版本：1.0（2026-10-31）
> 状态：done（100 篇 ratio 待复跑）
> 依赖：无（可与 M3 并行）
> 目标：让 100 篇报告有真实 metadata 和 ≥30% 全文，而不是 5 篇全文 + 只有 ID。

---

## 1. 目标

当前：

```text
100 篇
5 篇全文
metadata 只有 paper_id/title/abstract
paper index 只有 ID
```

Phase 4：

```text
OpenAlex/arXiv
  → metadata 完整
  → PDF/HTML/abstract 分层
  → fulltext ≥30%
  → paper index 可读
```

---

## 2. 边界

### 改

```text
src/lit_agent_v2/domains/report/openalex.py
src/lit_agent_v2/domains/report/ingest.py
src/lit_agent_v2/domains/report/pdf.py
src/lit_agent_v2/domains/report/source.py
src/lit_agent_v2/domains/report/contracts.py
```

### 不改

- claim；
- map/write；
- API。

---

## 3. Metadata

`Paper` 必须包含：

```json
{
  "paper_id": "W...",
  "title": "...",
  "authors": ["..."],
  "venue": "ACL",
  "year": 2025,
  "url": "https://...",
  "pdf_url": "https://...",
  "html_url": "https://...",
  "source": "openalex"
}
```

规则：

- title 缺失 → 拒绝进入 index；
- authors 缺失 → `metadata_missing=true`；
- year/venue 缺失 → 记录，不伪造；
- doi/url 至少一个。

### OpenAlex 字段

```text
id
title
authorships[].author.display_name
primary_location.source.display_name
publication_year
doi
best_oa_location.pdf_url
primary_location.landing_page_url
abstract_inverted_index
```

---

## 4. Fulltext

获取顺序：

```text
1. OA PDF
2. HTML landing page
3. abstract-only
```

记录：

```json
{
  "fulltext_available": true,
  "fulltext_source": "pdf|html|abstract",
  "fulltext_chars": 12000,
  "fulltext_error": null
}
```

规则：

- abstract 不得标 fulltext；
- 坏 PDF 不阻断整篇；
- 扫描 PDF 无文本层 → abstract-only；
- 100 篇中至少 30 篇 fulltext，否则 degraded。

---

## 5. 多源

Phase 4 至少：

```text
OpenAlex
arXiv（可选）
```

后续：

```text
Semantic Scholar
Unpaywall
```

本 phase 可只做 OpenAlex + HTML fallback，但必须把接口留成 adapter。

---

## 6. 指标

| 指标 | 目标 |
|---|---|
| `metadata.completeness` | ≥0.9 |
| `metadata.authors_rate` | ≥0.9 |
| `fulltext.available_ratio` | ≥0.3 |
| `fulltext.pdf_rate` | 记录 |
| `fulltext.html_rate` | 记录 |
| `source.coverage` | ≥0.8 |
| `source.duplicate_rate` | <0.1 |
| `source.http_error_rate` | <0.1 |

---

## 7. 事件

```text
source.paper.fetched
source.fulltext.attempted
source.fulltext.failed
source.fulltext.ready
```

payload：

```json
{"paper_id": "...", "source": "pdf|html|abstract", "chars": 1000, "error": null}
```

---

## 8. 测试

```text
tests/v2/test_m2_metadata.py
tests/v2/test_m2_fulltext.py
```

fixture：

- 完整 metadata；
- 缺 authors；
- 缺 title；
- PDF 正常；
- PDF 404；
- 扫描 PDF；
- HTML fallback；
- 重复论文。

验收：

```text
1. 20 篇真实抓取；
2. title/authors/venue/year 完整率 ≥0.9；
3. 至少 6/20 全文（30%）；
4. 失败不伪造；
5. 指标落库。
```

Live：

```text
OpenAlex 20 篇 + PDF 3 篇
```

---

## 9. 失败模式

| 错误 | 处理 |
|---|---|
| 429 | backoff |
| PDF 404 | HTML |
| HTML 404 | abstract |
| 坏 PDF | abstract |
| 无 title | 拒绝 |
| 0 篇 | run degraded/failed |

---

## 10. 当前 → 目标

| 项 | 当前 | 目标 |
|---|---|---|
| 全文 | 5/100 | ≥30/100 |
| authors | 无 | 有 |
| index | 只有 ID | title/venue/year |
| HTML | 有接口 | 真实使用 |
| arXiv | 无 | 可选 |

---

## 11. 实施记录（2026-10-31）

已完成：

- `Paper.authors`；
- OpenAlex authors/doi/landing/pdf/html；
- title 缺失过滤；
- metadata completeness / authors rate；
- PDF → HTML → abstract 回退；
- ingest fulltext 写入修复；
- live OpenAlex 10 篇：metadata 10/10，fulltext 3/10。

未完成：

- 100 篇 fulltext ratio 复跑；
- arXiv/Semantic Scholar adapter；
- fulltext failure 指标。

## 12. Commit

```text
feat(M2-P01): add paper metadata and multi-source fulltext
```
