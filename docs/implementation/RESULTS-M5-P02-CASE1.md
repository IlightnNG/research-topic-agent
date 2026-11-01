# RESULTS · M5-P02 Case-001 抽样分析

> 日期：2026-11-01
> 范围：case-001 `agents / tool use agents`，100 篇候选
> 性质：AI-only 预标注抽样，不是 human gold
> 结论：**claim 可用作预标注；当前 direction / 去重 / 完整性不满足 gold 要求**

---

## 1. 模板规模

```text
papers          100
unique titles    92
duplicate groups  5
extra duplicates  8
empty abstracts   0
```

重复标题：

```text
2  Procedural Environment Generation for Tool-Use Agents
2  Persistent Teacher Anchoring for Tool-Using Agents
3  The Confidence Dichotomy: Analyzing and Mitigating Miscalibration...
3  ToolPRMBench...
3  Beyond Accuracy: A Cognitive Load Framework...
```

`paper_id` 全部唯一，但标题重复，说明 OpenAlex 同论文多记录。

---

## 2. 实际执行

由于 100 篇单次运行 API 延迟过高，实际做了两批真实论文：

```text
batch 1: papers 0-7
batch 2: papers 8-15
```

总计：

```text
16 papers
15 annotated
1 missing
24 claims
```

missing：

```text
W7204596063  Invocation-Level Reliability of Tool-Using Agents
```

---

## 3. 具体论文结果

### 3.1 有效 claim

`W88095936` — *A schematic representation for cognitive tool-using agents*

```text
relevance 5
direction D1 Tool
claim method importance 5
quote: "One of the major contributions ... computational architecture ... tool use ... plan generation."
```

分析：

- quote 原文命中；
- claim 是方法贡献，不是作者列表；
- 可作为预标注。

`W4416036673` — *Procedural Environment Generation for Tool-Use Agents*

```text
method  RandomWorld procedural generation pipeline
finding SFT/RL on synthetic RandomWorld improves benchmarks, SoTA NESTFUL
```

`W7161024840` — *An Executable Benchmarking Suite for Tool-Using Agents*

```text
method  executable benchmarking suite with evidence-admission contract
```

`W7202365551` — *Bench2Robust*

```text
method  scenario-controlled recoverability framework
finding BTM improves robustness by 16.8 points without retraining
```

`W7222948050` — *From Interruption to Recoverable Cancellation*

```text
method  TECC stopping/revocation mechanism
```

这些 claim：

- 与论文内容一致；
- quote 精确；
- 有方法/结论；
- 不是句子切片噪声。

### 3.2 明显问题

#### 重复论文

```text
W4416036673 = W7106851738
  Procedural Environment Generation for Tool-Use Agents
  same RandomWorld claims

W7211896499 = W7224409073
  Persistent Teacher Anchoring for Tool-Using Agents
  same PTA claims

W7123875997 = W7168419411
  The Confidence Dichotomy
```

后果：

- claim recall 被重复论文抬高；
- 方向规模被重复论文放大；
- gold 方向 F1 被污染。

#### 方向全部塌缩

15 篇已标注全部：

```text
D1 Tool
```

方向名来自标题高频词 `Tool`，模型把几乎所有论文都放进 D1。

后果：

- `direction_f1` 无意义；
- `cluster.count` / `max_share` 无意义；
- 不能用于 M4 方向评估。

#### 缺失行

`W7204596063` 没有 annotation，说明 batch 输出并不保证 100%。

#### importance 饱和

24 条 claims 中：

```text
importance 5  约 23/24
importance 4  约 1/24
```

重要性几乎全 5，无法做 weighted coverage。

#### relevance 饱和

已标注：

```text
relevance 4-5
mean 约 4.8
```

检索结果全部“相关”，无法评估检索精度。

---

## 4. 是否可用

### 可用部分

```text
claim 文本
claim quote
claim type
部分 relevance
```

具体：

- quote 由代码校验原文命中；
- claim 与论文内容一致；
- 可用于：
  - AI 预标注；
  - 人工审核起点；
  - claim 覆盖 smoke test；
  - 发现作者列表/截断问题。

### 不可用部分

```text
direction
full 100 completeness
importance weighting
relevance precision
human gold 声称
```

原因：

1. 方向全部 D1；
2. 100 篇未完整跑完；
3. 8 篇重复；
4. importance 饱和；
5. relevance 饱和；
6. AI-only，无人工裁决。

---

## 5. 对整个体系是否可用

### 可以

```text
开发期 smoke test
claim quote 校验
回归对照（修复后）
AI 预标注
```

### 不可以

```text
M5 scorecard 的 gold gate
direction F1
human-verified gold
Judge-human calibration
Phase 4 最终验收
对外声称 100 篇 gold
```

如果直接接入 scorecard：

```text
direction F1 会虚高/失真
claim recall 被重复论文放大
weighted coverage 被 importance=5 扭曲
```

---

## 6. 必须修复

1. **去重**
   - DOI；
   - normalized title；
   - first author + year；
   - 100 unique papers。

2. **方向**
   - 不要用标题高频词做 taxonomy；
   - 每 case 用 LLM 全量/分块生成 5–8 个语义方向；
   - 或 embedding 聚类 + LLM 命名；
   - 校验 min_size / max_share。

3. **完整性**
   - 不允许 batch 缺行；
   - 缺行必须单篇重试；
   - 仍失败则标记 `needs_review`，不能静默跳过。

4. **importance**
   - 重新定义 1–5；
   - 要求至少 3 个等级；
   - 全 5 的 case 拒绝。

5. **relevance**
   - 保留低相关论文；
   - 不要全部 4–5；
   - 至少覆盖 1–5。

6. **人工/审核**
   - 至少抽检；
   - 或明确 `ai-prelabel`，不进入 hard gate。

---

## 7. 结论

```text
AI claim 预标注：有可用信号
AI direction：当前不可用
AI gold：当前不可用于全体系验收
```

本次抽样证明：

- 双 LLM 抽 claim 是可行的；
- 但“100 篇模板 + 两模型”还不能直接变成 gold；
- 主要瓶颈不是 claim，而是 **去重、方向、完整性、评分分布**。

**状态：**

```text
ai-prelabel
not human gold
not eligible for M5 gate
```
