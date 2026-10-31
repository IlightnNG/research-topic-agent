# M2 · Source

> 模块 ID：M2
> 代码：`src/lit_agent_v2/domains/report/{openalex,ingest,pdf,source}.py`
> 目标：把 topic/query 变成可引用、可审计的论文集合。

---

## 1. 职责

- OpenAlex / arXiv / 本地 corpus 检索；
- query / venue / year / limit；
- 去重、merge、相关性排序；
- 下载 OA PDF/HTML；
- 提取全文；
- 提供 paper metadata；
- 生成 `SourceArtifact`。

不负责：

- claim 抽取；
- 方向聚类；
- report 写作；
- 评分。

---

## 2. 输入/输出

### 输入

```python
SourceRequest(
    topic_id,
    query,
    limit=100,
    from_year=None,
    venue_ids=None,
    focus_hint=None,
)
```

### 输出：SourceArtifact

```json
{
  "topic_id": "...",
  "query": "...",
  "papers": [{
    "paper_id": "...",
    "title": "...",
    "abstract": "...",
    "authors": ["..."],
    "venue": "...",
    "year": 2025,
    "url": "...",
    "pdf_url": "...",
    "html_url": "...",
    "source": "openalex"
  }],
  "readiness": {"requested": 100, "retrieved": 135, "relevant": 100},
  "provenance": {"strategy": "openalex", "retrieved_at": "..."}
}
```

---

## 3. 边界

### 允许

- `httpx`；
- `pymupdf`；
- source adapters；
- M1 storage（只写 source artifact）。

### 禁止

- 抽 claim；
- 聚类；
- 写报告；
- 直接改 `reports` 表；
- 让 metadata 为空却进入 `papers`。

---

## 4. 关键规则

1. **metadata 完整**
   - paper_id / title / year / venue / url 至少 3 项；
   - 缺 title 的论文不能进入 report index。

2. **全文**
   - fulltext_available 必须记录；
   - PDF → HTML → abstract fallback；
   - 不允许把 abstract 标成 fulltext。

3. **去重**
   - id 去重；
   - title 归一化去重；
   - merged_id 不能重复。

4. **来源可追溯**
   - 每个 paper 记录 source；
   - 每个 query 记录 retrieved_at；
   - 记录 requested/retrieved/relevant。

5. **不伪造**
   - 不足 100 篇 → readiness 如实写；
   - 不补假论文。

---

## 5. 指标

| 指标 | 目标 |
|---|---|
| `search.coverage` | ≥0.8 |
| `search.precision_at_20` | ≥0.8 |
| `search.topic_relevance` | ≥0.8 |
| `search.duplicate_rate` | <0.1 |
| `metadata.completeness` | ≥0.9 |
| `fulltext.available_ratio` | ≥0.3 |
| `ingest.failure_rate` | <0.1 |

当前问题：

- 100 篇只有 5 篇全文；
- metadata 未含 authors；
- relevance 无 gold。

---

## 6. 验收

Phase 收尾：

```text
1. 20/50/100 篇真实抓取；
2. id/title 去重；
3. metadata 完整性；
4. PDF/HTML 解析；
5. fulltext ratio 落库；
6. 失败不伪造；
7. 指标 gate；
8. 无 claim/map 逻辑。
```

---

## 7. 测试

```text
tests/v2/test_s2_adapters.py
tests/v2/test_s1_s2.py::test_s2_source_and_evidence
```

新增：

```text
tests/v2/test_m2_*.py
```

必须覆盖：

- OpenAlex 映射；
- 空结果；
- 429/5xx；
- 坏 PDF；
- 重复论文；
- HTML fallback。

---

## 8. 失败模式

| 错误 | 处理 |
|---|---|
| OpenAlex 429 | retry/backoff |
| PDF 404 | HTML fallback |
| PDF 无文本层 | abstract-only，记录 |
| 无标题 | 拒绝进入 index |
| 0 篇 | run failed/degraded |

错误码见 `docs/ERRORS.md`。

---

## 9. 当前状态

| 能力 | 状态 |
|---|---|
| OpenAlex | ✅ |
| local corpus | ✅ |
| PDF | ✅ |
| HTML fallback | ✅ |
| arXiv | ❌ |
| metadata authors | ❌ |
| 全文 30% | ❌ |
| 真实 relevance gold | ❌ |

---

## 10. 相关文档

- `docs/ARCHITECTURE.md`
- `docs/TODO.md`
- `docs/ERRORS.md`


---

## Phase docs

- [M2-P01-metadata-and-fulltext.md](M2-P01-metadata-and-fulltext.md)
