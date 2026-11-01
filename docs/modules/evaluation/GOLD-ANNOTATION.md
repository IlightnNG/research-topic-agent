# Gold Annotation Workflow

> 模块：M5 Evaluation
> 版本：1.0（2026-11-01）
> 目标：把 3 × 100 篇候选语料变成可冻结、可复跑的人工 gold。
> 原则：模板不是 gold；未填写、未校验的 CSV 不能进入评估。

---

## 1. 当前模板

已生成：

```text
D:\lit-agent-store\v2-eval\gold\template\
  dataset.json
  annotation-sheet.csv
```

规模：

```text
3 cases
100 papers / case
300 rows
no gold claims
```

对应语料：

```text
D:\lit-agent-store\v2-eval\gold\corpora\
  agents\
  retrieval\
  planning\
```

当前只有 abstract，没有全文。  
`source_text` 就是 annotation quote 的校验来源。

---

## 2. 文件说明

`dataset.json`：

```json
{
  "schema_version": 2,
  "status": "draft",
  "cases": [
    {
      "case_id": "case-001",
      "papers": [
        {
          "paper_id": "W...",
          "relevance": 0,
          "source_text": "...",
          "claims": []
        }
      ],
      "gold_directions": []
    }
  ]
}
```

`annotation-sheet.csv`：

```text
case_id
topic_id
paper_id
title
authors
venue
year
direction_id
direction_name
relevance_1_5
claim_1_text
claim_1_quote
claim_1_type
claim_1_importance_1_5
claim_2_text
claim_2_quote
claim_2_type
claim_2_importance_1_5
```

---

## 3. 角色

```text
A  第一标注
B  第二标注
C  adjudication
```

A 和 B 独立填写，不共享结果。

---

## 4. 标注步骤

### Step 1 · 预检

确认：

```text
rows = 300
cases = 3
papers/case = 100
claim columns empty
status = draft
```

### Step 2 · 复制双份

```text
annotation-sheet-a.csv
annotation-sheet-b.csv
```

不要直接改模板。

### Step 3 · 标 direction

每个 case 先分方向：

```text
5–8 directions（按 policy）
方向名只用任务/方法/数据集词
禁止作者名、venue、机构
```

在 CSV 的：

```text
direction_id
direction_name
```

填写。

例：

```text
D1  tool routing
D2  dense retrieval
D3  planning
...
```

### Step 4 · 标 relevance

```text
1  不相关
2  弱相关
3  相关
4  强相关
5  核心论文
```

### Step 5 · 标 claims

每篇 1–2 条：

```text
claim_text
claim_quote
claim_type
claim_importance
```

规则：

- quote 必须逐字出现在 `source_text`；
- 不写作者列表；
- 不写 references；
- 不写致谢；
- 不写截断句；
- 不写纯背景；
- type：
  ```text
  finding
  method
  dataset
  limitation
  background
  ```
- importance：
  ```text
  1 次要
  3 一般
  5 关键
  ```

### Step 6 · 单人编译

```python
from lit_agent_v2.evaluation.gold_annotation import compile_annotations

compile_annotations(
    "template/dataset.json",
    "annotation-sheet-a.csv",
    "gold-a/dataset.json",
    status="annotator-a",
)
```

B 同理。

编译会校验：

- 300 行全部存在；
- 无重复 paper；
- quote 原文命中；
- type 合法；
- importance 1–5；
- direction 非空；
- 每篇至少 1 claim。

### Step 7 · 双人一致性

对 A/B 的 relevance 和 claim 选择计算一致性：

```text
inter_annotator_kappa >= 0.6
```

低于 0.6：

- 重新定义 rubric；
- 标注分歧集；
- 重新计算；
- 不进入 judge calibration。

### Step 8 · adjudication

生成：

```text
annotation-sheet-adjudicated.csv
```

规则：

- 保留双方一致；
- 分歧由 C 决定；
- 不直接改 A/B 原始文件；
- 记录裁决原因。

### Step 9 · 最终编译

```python
compile_annotations(
    "template/dataset.json",
    "annotation-sheet-adjudicated.csv",
    "gold-final/dataset.json",
    status="adjudicated",
)
```

### Step 10 · 冻结

记录：

```text
dataset.sha
git commit
date
annotators
kappa
```

写入：

```text
docs/implementation/RESULTS-M5-P02.md
```

---

## 5. 目录建议

```text
D:\lit-agent-store\v2-eval\gold\
  corpora\
  template\
  annotator-a\
    annotation-sheet.csv
    dataset.json
  annotator-b\
    annotation-sheet.csv
    dataset.json
  adjudicated\
    annotation-sheet.csv
    dataset.json
```

---

## 6. 验收检查

```text
cases = 3
papers/case = 100
claims/paper = 1–2
quote_verbatim_rate = 1.0
direction coverage >= 0.8
inter_annotator_kappa >= 0.6
dataset sha fixed
```

---

## 7. 禁止

- 用 LLM 自动填 gold 当作人工金标；
- 用报告生成器自己的 claims 当 gold；
- 只标 20 篇然后复制；
- 修改已冻结 dataset；
- 把 draft template 当 GoldDataset 使用。

---

## 8. 相关代码

```text
evaluation/gold.py
evaluation/gold_template.py
evaluation/gold_annotation.py
evaluation/calibration.py
```


---

## 9. AI-only 预标注（当前采用）

如果暂时不做人工审核，可以运行双模型独立预标注：

```powershell
python -m lit_agent_v2.evaluation.gold_prelabel `
  --template "D:\lit-agent-store\v2-eval\gold\template" `
  --output "D:\lit-agent-store\v2-eval\gold\ai-prelabel" `
  --model-a deepseek-flash `
  --model-b deepseek-v4-pro `
  --batch-size 8
```

两个 annotator：

```text
ai-a  deepseek-flash
ai-b  deepseek-v4-pro
```

它们：

- 独立 direction 聚类；
- 独立 relevance 评分；
- 独立 claim 抽取；
- 独立 type / importance；
- 不共享上下文；
- 使用不同 prompt version。

输出：

```text
ai-prelabel/
  annotation-sheet-ai-a.csv
  annotation-sheet-ai-b.csv
  gold-ai-a/dataset.json
  gold-ai-b/dataset.json
  run-metadata.json
  cache-ai-a/
  cache-ai-b/
```

`run-metadata.json` 标记：

```text
status = ai-prelabel
warning = AI-only labels; not human-verified gold
```

### 重要限制

- 这是 **AI-only labels**，不是 human gold；
- 不能写成 `adjudicated`；
- 不能把 AI-AI 一致性当作 human kappa；
- 不能用于声称“人类金标”；
- 可用于：
  - 预标注；
  - 回归对照；
  - 发现明显错误；
  - 为后续人工审核缩小范围。

### 质量检查

运行后必须检查：

```text
gold-ai-a/dataset.json 可 load
gold-ai-b/dataset.json 可 load
quote_verbatim_rate = 1.0
每篇 1–2 claims
5–8 directions/case
direction coverage >= 0.8
```

如果某个 case 失败，保留 cache，重新运行即可续跑。
