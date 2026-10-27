# Phase 3.2 · Report 核心能力重构（生成 · 工作台 · 作者关联）

> **版本**：**2.4.0**（2026-10-26，S1–S8 已落地）
> **类型**：核心功能重构（不改双层架构；Chat 推迟到 3.3）
> **前置**：Phase 3.1 已收尾（`pytest 569`、`verify_phase3 13/13`、e2e 16）
> **定位**：Report 是系统核心产物 —— 面向科研的“周度研究地图 + 可跳转证据工作台”
> **原则**：代码控结构、LLM 控语义；每条事实可追溯；失败可降级；参数可调、日志可查。

---

## 0. 目标与非目标

### 0.1 目标

| # | 目标 |
|---|---|
| G1 | 报告从“claim 列表”升级为 **Overview / Directions / Deep Dives / Cross-cutting / Gaps / Index** 结构 |
| G2 | 每个方向有 **共同点、差异点、代表论文、开放问题**，且全部带 claim 引用 |
| G3 | 引用 `[C#]` 可点击 → 中间打开 **Paper Tab**；Report/Trajectory 固定不可关 |
| G4 | 右侧可折叠面板：目录、引用论文、claims、**作者面板（简化 paper–author）** |
| G5 | 生成语言可选（English / 中文），默认 English |
| G6 | 支持几十到上百篇论文：批量预处理、缓存、聚类、懒加载、分页/虚拟列表 |
| G7 | 全流程参数可调、步骤可观测、错误可定位、失败可降级 |

### 0.2 非目标（本阶段不做）

| 项 | 去向 |
|---|---|
| Chat 流式/可恢复、引用抽屉、轨迹分组 | phase3.3 |
| 团队/实验室检测、全局知识图谱、作者消歧 UI | P4（3.2 只做 paper–author） |
| 双 Tab 拖拽并列（split/dock） | 3.2b 可选，先单 pane |
| PDF 批注、划词、Zotero | P4 |
| 自动生成图表、PDF 导出 | P4 |

---

## 1. 现状与设计判断

### 1.1 实测问题

最新报告：**4 claims / 303 字符**，结构为“标题 + N findings + 4 行 bullet + refs”。

| 问题 | 根因 |
|---|---|
| 报告太短 | `report` 只渲染 claims，没有综合 |
| 没有方向 | 只有 `Findings N`，无聚类/对比/缺口 |
| claim 太少 | 每篇 1 条（确定性）或全局 3–8 条（LLM） |
| 无语言选择 | 模板仅英文；生成页无 language 参数 |
| 无作者关联 | 有 `authors/paper_authors`，但 UI 未暴露 |
| 不可调、不可观测 | 没有 report 级配置、步骤日志、失败原因 |

### 1.2 核心判断

**Report 不是“一次 LLM 生成”，而是一条“预处理 → 聚类 → 综合 → 校验”的流水线。**

- LLM 只做：抽取、命名、描述、对比、写作；
- 代码负责：ID、引用表、聚类算法、字段校验、quote 校验、降级；
- 报告是“证据地图”，不是自由散文。

---

## 2. 目标架构

```text
┌──────────────────────────── Report Stage（外层 10 节点之一）────────────────────────────┐
│                                                                                         │
│  ① preprocess          ② claims            ③ cluster           ④ synthesize            │
│  PaperCard（每篇）  →   claim_id/quote  →   directions      →   directions/deep dives  │
│  批量 + 缓存           代码校验               算法 + 最小簇        LLM + claim 引用       │
│                                                                         │               │
│  ⑤ compare             ⑥ assemble           ⑦ validate          ⑧ persist              │
│  矩阵/差异              sections/refs       硬门禁 + 修复一次     两阶段提交 + 指标       │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                │
                ▼
        Report Workspace（前端）
  左：Run 列表    中：固定 Report/Trajectory + 动态 Paper Tab    右：Outline/Citations/Author
```

### 2.1 与现有图/微运行时关系

| 选择 | 结论 |
|---|---|
| 是否新增顶层节点？ | **不新增**。Report 仍是 10 节点之一，内部做子流水线 |
| 为什么？ | 保持 10 阶段契约、UI、golden、e2e、H 判据不变；避免状态膨胀 |
| 子步骤如何观测？ | `PHASE_CHANGE` stage=`report`，payload 增 `step/status/tokens/error_code`（只增字段，ADR-0006） |
| 是否用 MicroAgent？ | **不用 ReAct**。Report 是确定性多阶段流水线；仅在“校验失败修复”用一次有界循环 |
| 未来何时拆节点？ | 当 Chat 也要复用 PaperCard/聚类，或需要独立重试/门禁时，提升为 `report_prepare/report_synthesize/report_validate` |

---

## 3. 数据模型与迁移

### 3.1 新表

| 表 | 字段 | 用途 |
|---|---|---|
| `paper_cards` | `paper_id PK, content_sha, version, card_json, created_at` | 每篇论文结构化卡片缓存 |
| `report_steps` | `id, run_id, report_id, step, status, duration_ms, tokens, cost_usd, error_code, meta_json, created_at` | 子步骤日志/指标/排错 |
| `reports`（扩列） | `language, generated_by, word_count, fallback_reason` | 报告元信息 |
| `papers`（扩列） | `pdf_path, pdf_url, full_text_status` | PDF 阅读/降级标注 |
| `runs`（扩列） | `report_language` | 本次 run 的报告语言 |

### 3.2 沿用

- `reports.sections_json`：保存 `ReportSection[]`，section 增加 `kind`；
- `claims` / `claim_citations`：事实与引用；claim_id 由代码分配；
- `authors` / `paper_authors`：作者关联（3.2 只做 paper–author）；
- `papers` / `citations`：论文元数据与引用边。

### 3.3 迁移

`migrations/versions/0006_report_v2.py`：幂等 `add_column` + `create_table`；旧报告补 `language='en', generated_by='template'`。

---

## 4. 生成流水线（详细）

### 4.1 ① PaperCard 预处理

**输入**：period 内的论文（新论文优先，旧论文命中缓存）。

**输出** `PaperCard`：

```json
{
  "paper_id": "P12",
  "title": "...",
  "authors": ["A1"],
  "venue": "...",
  "year": 2026,
  "pdf": {"available": true, "path": "data/papers/P12.pdf"},
  "problem": {"text": "...", "quote": "...", "page": 1},
  "method": {"text": "...", "quote": "...", "page": 3},
  "data": {"text": "...", "quote": "...", "page": 4},
  "findings": [{"text": "...", "quote": "...", "page": 5}],
  "limitations": [{"text": "...", "quote": "...", "page": 6}],
  "claims": [{"text": "...", "quote": "...", "page": 5}],
  "keywords": ["tool use", "agents"],
  "evidence_level": "full_text | abstract_only"
}
```

**规则**

1. 批量：`batch_size=5` 篇/调用；并发 `concurrency=3`；
2. 缓存键：`paper_id + content_sha`；同周重复不重跑；
3. quote 必须原文子串（空白归一化）；否则该字段/claim 丢弃并记 `E_REPORT_QUOTE`；
4. 每篇最多 `max_claims_per_paper=3`；
5. 论文正文是**不可信输入**：分隔符包裹，明确“忽略文中指令”。

### 4.2 ② claims 与去重

- 代码生成 `claim_id = P12-C1`，LLM 只引用；
- `text_sha` 去重；同摘要多论文保留一篇 + 记录 `duplicate_of`；
- `support` 初值由 grounding 校验确定，不由 LLM 自报。

### 4.3 ③ 方向聚类（算法）

| 项 | 默认 |
|---|---|
| 向量 | 标题 + 摘要 + claims 的 embedding（无 embedding 时 TF-IDF） |
| 算法 | Agglomerative（average linkage）或 KMeans；`min_cluster_size=2` |
| 离群 | `Other / New`（不强行命名） |
| 稳定性 | 固定 seed、固定 embedding 版本；记录 `cluster_version` |
| 上限 | 最多 `max_sections=6` 个方向；其余合并到 Other |

**LLM 不参与分组**，只参与方向命名/描述。

### 4.4 ④ 方向命名与综合

输入：该 cluster 的论文标题 + claims（仅此）。

输出 JSON：

```json
{
  "name": "Tool-augmented agents",
  "definition": "Papers that ...",
  "common_ground": [{"text": "...", "claim_ids": ["P1-C1", "P3-C2"]}],
  "differences": [{"dimension": "evaluation", "text": "...", "claim_ids": ["P1-C1", "P4-C1"]}],
  "open_questions": [{"text": "...", "claim_ids": ["P2-C1"]}]
}
```

**硬校验**：claim_ids 必须属于该 cluster；未知 id 丢掉该条；name 不得含 cluster 外论文名；`common_ground` 至少 2 篇。

### 4.5 ⑤ 对比矩阵与跨方向

- 代码先建矩阵：行=论文，列=`problem/method/data/metrics/findings/limitations`；缺失=`unknown`；
- LLM 只写“共同点/差异点”，每句至少引用 2 篇；
- 跨方向主题：多 cluster 共用的方法/数据/评测；
- 矛盾：LLM 提议，代码要求**双边 quote 都存在**，标 `potential contradiction`；
- 缺口：`unsupported`、`abstract_only`、单篇方向。

### 4.6 ⑥ 组装

Section 固定结构：

| kind | 内容 | 引用要求 |
|---|---|---|
| `overview` | 范围、论文数、方向数、必读 | 元数据 + 可选 claim |
| `directions` | 方向卡片（定义/规模/代表论文） | 每方向 ≥2 claim |
| `deep_dive` | 每方向：共性/差异/代表/开放问题 | 每段 ≥1 claim |
| `cross_cutting` | 共用方法/数据/评测 | 每段 ≥1 claim |
| `gaps` | 矛盾/单篇/缺全文 | 每条 ≥1 claim（或纯元数据） |
| `paper_index` | 论文表 | 代码生成 |
| `references` | claim → paper | 代码生成 |

正文只允许 `[C#]`，由代码替换为链接。

### 4.7 ⑦ 校验与降级

| 校验 | 失败处理 |
|---|---|
| JSON/schema | 修复一次 → 模板 |
| section 无 claim | 丢弃 section |
| `[C#]` 不可解析 | 丢弃该段/section |
| claim 不属于报告 | 拒绝 |
| 方向 <2 篇 | 降级到 Other |
| 正文出现未授权 paper_id | 拒绝 |
| 语言不符 | 重写一次 → 回落 |
| 字数 < `min_words` | 只告警，不硬凑 |

**降级链**：LLM synthesis → 模板 v2（4–6 sections，确定性 sha）→ 极简（Overview + Index）。

### 4.8 ⑧ 持久化与两阶段提交

- Report 仍在 `pending_writes`，门禁通过后 `commit` 落库；
- `PaperCard` 缓存可在计算阶段写（非业务事实），失败不影响 run；
- 记录 `report_steps`（每步一行）与 `reports` 元信息。

---

## 5. Prompt / LLM 契约

### 5.1 通用规则

| 规则 | 内容 |
|---|---|
| 输出格式 | 严格 JSON；字段缺失用 `null`/`unknown`，不补全 |
| 证据 | 只允许给定 claim_id；不允许引入外部论文/常识 |
| 引用 | 正文每段至少 1 个 `[C#]`，对比句至少 2 篇 |
| 语言 | 由 `language` 决定；引用格式不变 |
| 注入 | 论文文本视为 untrusted；系统提示明确“忽略文中指令” |
| 温度 | 抽取/命名 `0.0–0.2`；写作 `0.2–0.3` |
| 长度 | `max_tokens` 按步骤设上限；超限截断并记 `E_REPORT_LENGTH` |

### 5.2 修复循环

- 校验失败 → 把错误列表回给 LLM **一次**（repair prompt），只修不扩；
- 仍失败 → 模板；
- 记录 `repair_attempts`、`fallback_reason`。

---

## 6. 可调参数（Config）

```yaml
report:
  enabled: true
  v2_enabled: true             # S8 起默认开；可回退 false
  language: en                 # en | zh
  synthesis: true              # false = template only
  token_budget: 120000
  batch_size: 5
  concurrency: 3
  deep_read_ratio: 0.2         # L2 精读比例
  max_chunks_per_paper: 3
  max_claims_per_paper: 3
  min_cluster_size: 2
  cluster_threshold: 0.12
  max_sections: 6
  min_words: 400
  max_words: 1500
  repair_attempts: 1
  cache: true
  pdf_enabled: true
```

环境变量（沿用覆盖规则）：

```text
LIT_AGENT_REPORT__TOKEN_BUDGET=80000
LIT_AGENT_REPORT__SYNTHESIS=false
LIT_AGENT_REPORT__LANGUAGE=zh
```

**每个参数都进 metrics/日志**，便于后续 A/B 与调参。

---

## 7. 日志、指标与错误处理

### 7.1 事件

不新增 EventType（ADR-0006）：

```json
{
  "type": "phase_change",
  "stage": "report",
  "payload": {
    "phase": "step",
    "step": "preprocess|cluster|synthesize|validate|persist",
    "status": "start|ok|failed|fallback",
    "duration_ms": 123,
    "tokens": 456,
    "error_code": "E_REPORT_SCHEMA"
  }
}
```

### 7.2 `report_steps` 表

每步一行：`step/status/duration_ms/tokens/cost/error_code/meta_json`；用于 UI 排错与论文指标。

### 7.3 错误码

| 错误码 | 含义 | 处理 |
|---|---|---|
| `E_REPORT_SCHEMA` | JSON/schema 失败 | 修复一次/模板 |
| `E_REPORT_CITATION` | `[C#]` 无法解析 | 丢 section |
| `E_REPORT_QUOTE` | quote 非原文 | 丢 claim |
| `E_REPORT_CLUSTER` | 聚类失败/全离群 | 关键词分组 |
| `E_REPORT_LLM` | 模型调用失败 | 模板 |
| `E_REPORT_LANGUAGE` | 语言不符 | 重写/模板 |
| `E_REPORT_EMPTY` | 无证据 | `No citable evidence` |

### 7.4 日志字段

`run_id/report_id/step/status/duration_ms/tokens/cost_usd/error_code/model/prompt_version/fallback_reason`；**不记录 prompt 正文、论文全文、密钥**。

---

## 8. 前端工作台

### 8.1 布局（修正版）

```text
┌──────────────┬──────────────────────────────────────────────┬──────────────┐
│ Runs 列表     │ Tab: [Report] [Trajectory] [P12] [P15]…     │ Right Panel  │
│（可折叠）     │ ┌──────────────────────┬───────────────────┐ │（可折叠）     │
│              │ │ 主 Tab               │ 并列 Tab（P2）    │ │ Outline      │
│              │ │ Report / Paper       │ Paper             │ │ Citations    │
│              │ └──────────────────────┴───────────────────┘ │ Author       │
└──────────────┴──────────────────────────────────────────────┴──────────────┘
```

### 8.2 Tab 规则

| 规则 | 说明 |
|---|---|
| 固定 | `Report`、`Trajectory` 不可关闭，始终在 |
| 动态 | 论文 Tab `paper:P12`，可关闭 |
| 去重 | 同一论文只开一个；重复点击 = 激活 |
| 关闭 | 关闭后激活相邻 Tab；固定 Tab 永不可关 |
| 切 run | Report/Trajectory 更新；论文 Tab 清空（避免串数据） |
| 状态 | `sessionStorage` per run；URL `?tab=paper:P12` 可恢复 |
| 上限 | 最多 8 个论文 Tab，LRU |
| 并列 | P2：`splitpanes` + 自定义拖拽；P0 不做 |

### 8.3 引用 → Paper Tab（核心）

```text
[C3] → claim → paper_id
  → 已有 tab：激活
  → 无 tab：新建 paper:P12，带 claim/quote 定位
  → 普通点击：当前 pane；Cmd/Ctrl+点击：右侧 pane（P2）
```

### 8.4 Report 页面

- TOC（右侧）+ 当前 section 高亮；
- 渲染 `kind` 对应块；`paper_index` 表格分页；
- 引用 chip：`[C3]`/`[P12]` → 打开 Paper Tab；
- 报告元信息：language / generated_by / words / claims；
- 空证据：`No citable evidence`，不渲染空 Findings；
- 旧报告兼容：`sections=[]` 时回落 Claims 表。

### 8.5 Paper Tab

- 标题/作者/venue/年份；作者可点击；
- 摘要/全文；PDF（`iframe#page=` 或 `vue-pdf-embed`）；
- 该论文在报告中的 claims；被哪些 section 引用（backlinks）；
- 同作者其他论文（简化关联）；
- 无 PDF：显示 abstract + `abstract_only` 标记 + 下载/来源链接。

### 8.6 作者关联（简化 paper–author）

| 交互 | 行为 |
|---|---|
| 点击作者名 | 右侧切到 **Author**，不新开 Tab |
| 面板内容 | 姓名、论文数、本周新增、最近论文、合作者（可选） |
| 论文项 | 点击 → 打开 Paper Tab |
| 返回 | 面板内返回栈 |
| 范围 | **只做 paper–author**；团队/实验室/全局图 P4 |

### 8.7 右侧面板

```text
Outline | Citations | Author | Claims
```

- 可折叠（按钮 + 快捷键）；小屏自动隐藏；
- Outline：section 跳转；
- Citations：当前 section 的论文（去重）；
- Claims：support 状态、点击定位；
- Author：见 8.6。

---

## 9. API 契约

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/topics/{id}/run` | body 增 `report_language` |
| GET | `/api/reports/{id}` | sections、元信息、claims 映射 |
| GET | `/api/reports/{id}/steps` | 子步骤日志（调试/指标） |
| GET | `/api/papers/{id}` | 元数据、authors、claims、pdf 状态 |
| GET | `/api/papers/{id}/pdf` | Range 响应；无文件 404 + 原因 |
| GET | `/api/authors/{id}` | 姓名、论文数、最近论文、合作者 |
| GET | `/api/authors/{id}/papers` | 该作者论文列表 |

错误统一沿用 `E_*`；`message` 默认英文。

---

## 10. 库选型（先搜后用）

| 需求 | 方案 | 许可证 | 决策 |
|---|---|---|---|
| 固定/动态 Tab、关闭、去重 | Vue + Pinia 自研 | — | **自研**（S，200–300 行） |
| 引用解析 `[C#]` | 正则 + 代码 | — | **自研** |
| 右侧折叠/目录 | Element Plus + IntersectionObserver | MIT | 复用现有 |
| Markdown 渲染 | `markdown-it` + `DOMPurify` | MIT / Apache-2.0 | 用库 |
| PDF 阅读 | 先 `iframe#page=`；后 `vue-pdf-embed` + `pdfjs-dist` | MIT / Apache-2.0 | 用库 |
| 双栏并列 | `splitpanes` | MIT | P2 再用 |
| 完整 dock/拖拽 | `dockview-vue` | 需复核 | 备选，不首选 |
| 长列表 | `@tanstack/vue-virtual` | MIT | 100+ 再用 |
| 图谱 | `@vue-flow/core` | MIT | P4，不自研 |
| 聚类 | `scikit-learn`（Agglomerative/KMeans） | BSD-3 | 用库；BERTopic 可选但重 |
| JSON 校验 | Pydantic（已有） | MIT | 用库 |
| 论文卡片/报告文本 | 无现成库 | — | 自研 prompt + 校验 |

**规则**：Tab/引用自研；PDF/分屏/虚拟/图谱/聚类用库；不为了一个功能引入整套框架。

---

## 11. 实施步骤

### 3.2a · 核心（建议先做，≈10 天）

| 步 | 内容 | 验收 |
|---|---|---|
| S1 ✅ | 数据模型 + 迁移 0006 + `ReportSettings` | 26 张表；health 一致；旧报告可读 |
| S2 ✅ | PaperCard 预处理 + 缓存 + quote 校验 | `report/cards.py`；9 例；坏 quote 丢弃、LLM 失败回落 |
| S3 ✅ | claims 去重 + claim_id + 每篇 ≤3 | `report/claims.py`；重复/超限测试 |
| S4 ✅ | 聚类 + 方向命名 | `report/clusters.py` + `context.py`；阈值可调；离群进 Other |
| S5 ✅ | 方向综合 + 对比 + 缺口 | `report/synthesis.py`：common/differences/open_questions；claim_id 白名单；失败逐方向回落 |
| S6 ✅ | 组装 + 校验 + 两阶段提交 | `report/assemble.py`；v2 走 `pending_writes.draft`；校验失败模板回落 |
| S7 ✅ | 报告指标 + 门禁 | `eval/report_metrics.py`；`gate_report_contract` 校验 draft |
| S8 ✅ | 报告页 sections/TOC/引用 chip + Paper Tab | `.cite-chip` → 论文 Tab；PaperPane + `/api/papers/{id}` |
| S9 | e2e + 回归 | 固定 Tab/引用/关闭/切 run |

### 3.2b · 体验（≈6 天）

| 步 | 内容 | 验收 |
|---|---|---|
| S10 | Paper Tab + PDF/下载 | 有 PDF 可读；无则 abstract |
| S11 | 作者面板（paper–author） | 点击作者显示其他论文 |
| S12 | 语言选择（生成页） | en/zh 均出报告 |
| S13 | 长列表分页/虚拟 | 100 篇不卡 |
| S14 | 收尾文档 | H1–H15 |

### 3.2c · 可选（P2）

- 双 pane 并列（splitpanes + 拖拽）；
- 作者×方向矩阵；
- ego graph。

---

## 12. 验收（H1–H15）

| # | 判据 |
|---|---|
| H1 | 报告含 ≥4 sections（Overview/Directions/Deep Dive/Gaps） |
| H2 | 每个正文 section ≥1 claim；`[C#]` 全部可解析 |
| H3 | 无引用 section 被拒；坏报告不落库 |
| H4 | 模板路径 sha 稳定；LLM 失败回落不 500 |
| H5 | 方向 ≥2 篇；单篇进 Other |
| H6 | 每篇 ≤3 claim；重复 claim 去重 |
| H7 | 报告默认英文；zh 生成中文，引用不变 |
| H8 | quote 原文命中率 100%（丢弃失败项） |
| H9 | 报告页 TOC/sections/引用 chip 可用 |
| H10 | 点击引用 → Paper Tab；重复点击不重复开 |
| H11 | Report/Trajectory 固定不可关；关闭论文 Tab 回相邻 |
| H12 | 切换 run 清空论文 Tab |
| H13 | 作者面板显示该作者其他论文，可打开 Tab |
| H14 | 100 篇规模：报告生成不超 `token_budget`；列表不卡 |
| H15 | 回归：`pytest 569+`、`verify_phase3 13/13`、e2e 16+ |

### 测试命令

```powershell
. .\scripts\env.ps1
uv run pytest -q tests/report tests/gates tests/agents
cd web; npm run typecheck; npm run build
npx playwright test e2e/smoke.spec.ts -g "report|Report|paper" --reporter=line
```

---

## 13. 性能与规模

| 项 | 策略 |
|---|---|
| 100 篇 | 批处理 5 篇/调用；并发 3；缓存 PaperCard |
| token | `token_budget` 控制；L2 精读 20%；超限截断并记录 |
| 报告页 | 首屏只渲染 Overview/Directions；Deep Dive 懒加载 |
| 论文表 | 分页（默认）；100+ 启用虚拟列表 |
| PDF | 按需加载；Range；LRU 缓存 |
| 聚类 | 固定 seed/版本；可缓存 cluster 结果 |

---

## 14. 风险与回滚

| 风险 | 缓解 |
|---|---|
| LLM 编造 | 只允许 claim_id；quote 校验；无引用 section 拒绝 |
| 聚类不稳 | 固定 seed；记录版本；人工可改名（P4） |
| 迁移破坏旧数据 | 0006 幂等；旧报告补默认值 |
| 生成超时 | 子步骤超时；失败回落模板；不阻塞 run |
| 作者同名 | 3.2 只展示现有 author_id；标注“可能重复”（P4 消歧） |
| 成本上升 | 批量 + 缓存 + token 预算 + 一次修复 |
| 回滚 | `alembic downgrade 0005_chat_reason`；`report.synthesis=false` |

---

## 15. 手工验收（10 分钟）

1. 生成英文报告 → 至少 4 sections，引用可点；
2. 点 `[C3]` → 中间出现 Paper Tab；Report 仍在；
3. 关闭 Paper Tab → 回到 Report；
4. 点作者 → 右侧 Author 显示其他论文；点论文开 Tab；
5. 切到另一条 run → 论文 Tab 清空；
6. 生成中文报告 → 中文正文、引用不变；
7. 无证据 topic → `No citable evidence`；
8. `LIT_AGENT_REPORT__SYNTHESIS=false` → 模板 v2 仍可读。

---

## 16. 参考（开源项目）

| 项目 | 借什么 |
|---|---|
| PaperQA2 | 证据充分性、in-text citation、拒答 |
| assistant-ui | 原语化 UI、引用/工具卡片组合 |
| LibreChat | 报告/轨迹分节、阅读工作台 |
| dockview / splitpanes | 并列布局（P2） |
| RAGAS | faithfulness / context precision（S7） |
| 调研全文 | `open-source-borrowing-survey.md` |

---

## 17. 变更记录

| 版本 | 日期 | 内容 |
|---|---|---|
| 2.4.0 | 2026-10-26 | S7–S8 落地：报告指标/门禁、paper API、引用 chip、动态 Paper Tab；v2 默认开；修复报告阶段嵌套写锁与 claim id 不一致 |
| 2.3.0 | 2026-10-26 | S5–S6 落地：方向综合（claim 白名单/回落）、报告组装与硬校验、v2 两阶段提交（`report.v2_enabled` 默认 false） |
| 2.2.0 | 2026-10-26 | S3–S4 落地：claim 规范化/去重、轻量 Jaccard 聚类、方向命名、ReportContext 装配；`cluster_threshold` 可调 |
| 2.1.0 | 2026-10-26 | S1–S2 落地：0006 迁移（26 表）、ReportSettings、PaperCard 缓存/quote 校验/LLM 回落 |
| 2.0.0 | 2026-10-26 | 重构：生成子流水线、Tab 工作台、作者关联、参数/日志/错误、库选型、S1–S14、H1–H15 |
| 1.0.0 | 2026-10-26 | 首版：报告结构/合成/语言/指标 |
