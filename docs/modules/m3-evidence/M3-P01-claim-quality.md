# M3-P01 · Claim Quality

> 模块：M3 Evidence
> 版本：1.0（2026-10-31）
> 状态：done
> 依赖：M1-P01（LLM client）
> 目标：让 claim 是 research claim，而不是句子切片、作者列表或参考文献。

---

## 1. 目标

当前：

```text
句子 → claim
purity 恒 1
作者列表被接受
```

Phase 4：

```text
paper text
  → candidate sentence
  → type classifier (LLM + rules)
  → quote exact check
  → claim schema
  → purity 计算
```

---

## 2. 边界

### 改

```text
src/lit_agent_v2/domains/report/claim_extractor.py
src/lit_agent_v2/domains/report/evidence.py
src/lit_agent_v2/domains/report/contracts.py
```

### 不改

- source/ingest；
- map/write；
- API。

---

## 3. Claim schema

```json
{
  "claim_id": "P1-C1",
  "paper_id": "P1",
  "text": "...",
  "quote": "...",
  "section": "abstract|fulltext",
  "page": 1,
  "claim_type": "finding|method|dataset|limitation|background",
  "confidence": 0.8,
  "is_research": true
}
```

规则：

- `quote` 必须原文命中；
- `text` 不得是 quote 的简单截断；
- 作者列表/参考文献/致谢/版权 → reject；
- 无主语/谓词 → reject；
- `background` 不计入 research claim。

---

## 4. Claim 类型

| type | 定义 | 计入 purity |
|---|---|---|
| finding | 研究结论 | ✅ |
| method | 方法/架构 | ✅ |
| dataset | 数据集/benchmark | ✅ |
| limitation | 局限 | ✅ |
| background | 背景/动机 | ❌ |

---

## 5. LLM prompt

```text
Extract research claims from the paper text.
Every claim must have an exact verbatim quote.
Reject author lists, affiliations, references, acknowledgements, copyright.
Classify each claim:
finding | method | dataset | limitation | background.
Return JSON:
{"claims":[{"text":str,"quote":str,"type":str,"confidence":0..1}]}
```

后处理：

- quote not in text → reject；
- type invalid → background；
- author regex → reject；
- truncation → reject。

---

## 6. 规则过滤

```python
AUTHOR_LIST = 3+ capitalized names separated by comma/and
REFERENCE = "et al.", "In Proceedings", "pp.", "arXiv:"
ACK = "we thank", "funded by"
TRUNCATED = sentence ends with "as", "the", "of", "and", "algorit"
```

更稳：

- 需要至少一个 claim 动词：show / find / improve / propose / achieve / reduce / increase / outperform；
- 需要长度 ≥ 8 words；
- 需要完整标点。

---

## 7. 指标

| 指标 | 目标 |
|---|---|
| `claim.purity` | ≥0.98 |
| `claim.citation_coverage` | 1.0 |
| `claim.nonresearch_rate` | 0 |
| `card.quote_verbatim_rate` | 1.0 |
| `claim.count_per_paper` | 1–2 |
| `claim.duplicate_rate` | <0.1 |

purity：

```text
research_claims / all_claims
```

必须真实分别计数。

---

## 8. 事件

```text
claim.extracted
claim.rejected
claim.purity.updated
```

payload：

```json
{"paper_id": "P1", "claim_id": "P1-C1", "type": "finding", "reason": null}
```

---

## 9. 测试

```text
tests/v2/test_m3_claim_types.py
tests/v2/test_m3_author_lists.py
tests/v2/test_m3_quotes.py
```

fixture：

- 正常 finding；
- 作者列表；
- references；
- acknowledgement；
- 截断句；
- 背景句；
- quote 不存在；
- duplicate claim。

验收：

```text
- 作者列表 100% 拒绝；
- 截断 100% 拒绝；
- purity 负样本 <0.98；
- 正常样本保留；
- 每条 claim 有 type。
```

---

## 10. 当前 → 目标

| 项 | 当前 | 目标 |
|---|---|---|
| claim 类型 | 无 | 5 类 |
| 作者过滤 | 无 | regex + LLM |
| purity | 恒 1 | 真计算 |
| quote 截断 | 接受 | 拒绝 |
| background | 计入 | 排除 |

---

## 11. 回滚

- 保留 deterministic extractor；
- LLM 失败 → fallback；
- 但 fallback 必须同样过滤作者/截断。

---

## 12. 实施记录（2026-10-31）

已完成：

- 5 类 claim；
- 作者/refs/ack/copyright/truncation 过滤；
- quote exact；
- research claim 计数；
- LLM claim extractor；
- live LLM 测试；
- `claim_type` contract v1.1。

未接入：

- M4 writer 仍使用 deterministic extractor；
- nonresearch rate 未单列 metric。

## 13. Commit

```text
feat(M3-P01): add typed claims and author-list rejection
```
