# M3 · Evidence

> 模块 ID：M3
> 代码：`src/lit_agent_v2/domains/report/{evidence.py,claim_extractor.py,contracts.py}`
> 目标：把论文变成可核验的 claim + quote，不允许“句子切分即 claim”。

---

## 1. 职责

- 构建 paper card；
- 读取 fulltext/abstract；
- 抽取 claim；
- 过滤非 research 文本；
- 绑定 exact quote / page / section；
- 计算 evidence 覆盖；
- 生成 `EvidenceArtifact`。

不负责：

- 检索论文；
- 聚类方向；
- 写报告；
- 评分体系。

---

## 2. 输出

```json
{
  "papers": [{
    "paper_id": "...",
    "title": "...",
    "abstract": "...",
    "level": "L1|L2",
    "fulltext_available": true,
    "quote_windows": [{"text": "...", "section": "...", "page": 1}],
    "claims": [{
      "claim_id": "...",
      "paper_id": "...",
      "text": "...",
      "quote": "...",
      "claim_type": "finding|method|dataset|limitation|background",
      "confidence": 0.8
    }]
  }],
  "coverage": {"papers": 100, "with_claims": 84, "fulltext": 5},
  "stats": {"quote_checks": 185, "quote_ok": 185, "claims": 185}
}
```

---

## 3. 边界

### 允许

- 读取 M2 `SourceArtifact`；
- 本地 PDF 文本；
- LLM claim extractor；
- exact quote 校验。

### 禁止

- 用 author list / references / acknowledgements 当 claim；
- 用截断句当 claim；
- 用 abstract 冒充 fulltext；
- 伪造 quote；
- 写方向/报告。

---

## 4. Claim 规则

### 必须是

- 有主语/谓词的研究陈述；
- 可由 quote 支持；
- 有 paper_id + quote + section/page；
- 类型明确。

### 必须拒绝

```text
作者列表
机构/地址
参考文献
致谢
版权
期刊/会议 metadata
截断句
纯短语
无 claim 动词的句子
```

### Claim 类型

```text
finding      研究结论
method       方法
dataset      数据集/benchmark
limitation   局限
background   背景（不计入 research claim）
```

`claim.purity` 只统计 research claim。

---

## 5. 指标

| 指标 | 目标 |
|---|---|
| `card.quote_verbatim_rate` | 1.0 |
| `claim.purity` | ≥0.98 |
| `claim.citation_coverage` | 1.0 |
| `claim.specificity` | judge ≥4 |
| `claim.duplicate_rate` | <0.1 |
| `fulltext.available_ratio` | ≥0.3 |
| `claim.count_per_paper` | 1–2 |
| `claim.nonresearch_rate` | 0 |

当前问题：

- purity 恒 1；
- 作者列表被接受；
- quote 截断；
- abstract claim 冒充 fulltext。

---

## 6. 验收

```text
1. 作者/参考文献样本全部拒绝；
2. quote 原文命中；
3. 截断句拒绝；
4. claim 类型正确；
5. purity 可复算；
6. 20/50/100 篇真实样本；
7. 指标落库；
8. 不写方向/报告。
```

---

## 7. 测试

```text
tests/v2/test_s1_s2.py
tests/v2/test_s2_adapters.py
```

新增：

```text
tests/v2/test_m3_claim_types.py
tests/v2/test_m3_quotes.py
```

fixture 必须包含：

- 正常 finding；
- 作者列表；
- references；
- 截断句；
- 无 quote；
- 非 research 陈述。

---

## 8. 失败模式

| 错误 | 处理 |
|---|---|
| quote 不存在 | 丢弃 claim |
| 作者列表 | 丢弃 |
| 截断 | 丢弃 |
| LLM 非 JSON | fallback deterministic |
| 0 claim | 该 paper 无 claim，记录 |

错误码见 `docs/ERRORS.md`。

---

## 9. 当前状态

| 能力 | 状态 |
|---|---|
| L1/L2 | ✅ |
| quote | ✅ |
| claim | ✅ |
| claim 类型 | ❌ |
| 作者过滤 | ❌ |
| purity 真计算 | ❌ |
| LLM extractor | ✅ 接口，未默认 |
| 全文 30% | ❌ |

---

## 10. 相关文档

- `docs/ARCHITECTURE.md`
- `docs/TODO.md`
- `docs/ERRORS.md`


---

## Phase docs

- [M3-P01-claim-quality.md](M3-P01-claim-quality.md)
