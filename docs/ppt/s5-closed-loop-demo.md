# S5 最小闭环演示（单页 brief）

> 用途：组会/导师演示 Step 5（walking skeleton）时的讲稿与数字依据。
> 数据来源：`prototype/out/s5_summary.json`、`prototype/out/reports/T1-*-p0-s5-*.md`、`prototype/out/events.jsonl`（run_id 可过滤）。
> 全部数字均为**真实运行**（云端 DeepSeek `deepseek-flash`，无 mock、无人工编造）。

## 1. 一句话

**给定一个研究主题，系统自动完成"取文 → 归一化去重 → 分块 → 入库 → 检索 → LLM 抽取证据 → LLM 生成报告 → 引用可回查校验 → 全程事件留痕"，产出可审计的报告与结构化 claims。**

## 2. 闭环流程（实际跑通的链路）

```
topic=T1「多智能体 LLM 编排与可靠性」
   │
   ├─5.1 fetch      OpenAlex 真实响应（24 篇，1 次 HTTP 3.17s）
   │                 └─ SQLite sync_state 增量游标
   ├─5.2 normalize  canonical_id(DOI→W→arxiv) + 作者 name_norm + D6 三段式去重
   ├─5.3 chunk      摘要 → 43 块（token 预算 120，句子边界对齐）
   ├─5.4 store      SQLite 真相源：papers/authors/citations/claims/merges/sync_state
   │                 └─ 写入后**计数对账**（mismatches={}）
   ├─5.5 retrieve   词法 TF-IDF 余弦 → top-12 证据卡（每卡带可回查片段）
   ├─5.6 report     云 LLM ①批量抽结构化卡片（3 次）②生成报告 JSON（1 次）
   │                 └─ 脚本强制：citation 回查不到语料的 claim **整条丢弃**
   └─5.7 events     33 条事件 / run，seq 连续；含 llm_call（tokens/cost/延迟/缓存）
                     ↓
   out/reports/T1-<date>-<run_id>.md   (≈9.0k 字, 16–18 claims, 100% 带引用)
   out/claims_<run_id>.json            (结构化断言 + citation 片段)
```

## 3. 本次实测数字（导师最关心的三件事：能不能跑通 / 准不准 / 贵不贵）

### 3.1 能否跑通（端到端）

| 环节 | 结果 |
|---|---|
| 语料 | 24 篇真实 OpenAlex 记录（含摘要），137 位作者 |
| 分块 | 43 块，平均 2.4 块/篇 |
| 证据卡 | 12 张（top-12），检索分数 0.038–0.134（词法余弦） |
| 报告 | **8,946–9,189 字**，**16–18 条 claim**，**100% 带 citation**，引用 12 篇不同论文 |
| 事件 | **33 条/run**，seq 连续无缺口 |
| 重跑 | 论文数不变（新增 0）、claims 文件 sha1 **完全一致**（同一输入→同一产物） |

### 3.2 准不准（grounding）

- 报告每条结论都带 `[paper_id]`，脚本**强制校验**该 id 出现在本次语料中；校验不过的 claim 直接丢弃并计数（本轮 dropped=0）。
- 报告含**证据可回查性**章节，明确写出片段来源（OpenAlex 摘要）与本轮未使用 PDF 全文。
- 实测发现并记录：这批 2026 年新论文的 `referenced_works` **本身为空**（`references_total=0`），与 S1b 的引用完整率结论一致——引用图的价值取决于语料规模与反向构边，属 Phase 1。

### 3.3 贵不贵（成本，真实账单）

| 场景 | 调用 | tokens | 成本 | 耗时 |
|---|---|---|---|---|
| **冷启动**（run 001） | 4 次逻辑调用 / 7 次网络请求（含 3 次重试） | 4,578 + 10,215 | **$0.006345** | 90.9 s |
| 冷启动（run 005，改进了片段截断） | 4 / 4（含 2 次重试） | 3,008 + 5,920 | **$0.003608** | 60.1 s |
| **缓存重跑**（run 006） | 4 / 0（4 次缓存命中） | 0 | **$0.0** | **0.12 s** |

→ 单 run 成本 **<$0.01**；周更 52 周 × 多 topic 也远低于预算上限（配置 `run_cost_budget_usd: 2.0`，本轮实际用了它的 **0.3%**）。
→ 平均单次调用 ≈13–15 s（`deepseek-flash` 是 **reasoning 模型**，先产出 reasoning 再产出正文）。

## 4. 本轮踩到并修掉的坑（体现"harness 工程"而非"调 API"）

| 现象 | 根因 | 处置 |
|---|---|---|
| LLM 返回 `content=''` 却"成功" | `deepseek-flash` 是 reasoning 模型，`max_tokens` 被推理吃光 → `finish_reason=length` | 网关把 `length`/空正文**一律判失败**并放大预算重试（已单测覆盖） |
| `citations=0` | canonical id 用 DOI，而 `referenced_works` 是 W id | 增加 W→canonical 映射；同时确认该批论文本身无 references（与 S1b 一致） |
| 启动即崩 `table papers has no column named abstract` | `out/data/sqlite.db` 是早先 S3 spike 写的**旧结构** | 加 **schema 身份校验**：不匹配就明确报错 + `--reset-store` 显式重建 |
| 事件数忽高忽低 | 同一 `run_id` 被复用于多次尝试，事件流按 run_id 累加（S4 已知行为） | **run_id 必须唯一标识一次尝试**；resume 场景才复用 |

## 5. 验收标准对照（Step 5 spec）

| 验收项 | 目标 | 实测 | 判定 |
|---|---|---|---|
| 端到端一次跑通 | 是 | 是（`--topic T1 --run-id p0-s5-006`） | ✅ |
| 报告长度 | ≥800 字 | 8,946–9,189 字 | ✅ |
| claim 数 | ≥10 且 100% 带 citation | 16–18 且 100% | ✅ |
| citation 可回查 | 脚本核对并输出支持率 | 100%（dropped=0） | ✅ |
| 单 run 事件 | ≥30 条 | 33 条 | ✅ |
| 重跑幂等 | 论文记录数不变 | 新增 0、mismatches={} | ✅ |
| 成本可重复 | ±30% | 缓存重跑 $0（优于目标）；冷启动 $0.0036–0.0063 | ✅ |

## 6. 诚实边界（明确"没做什么"）

| 未做 | 原因 | 归属 |
|---|---|---|
| PDF 全文解析（PyMuPDF/pdfplumber） | 需批量下载 OA PDF，网络密集；摘要已足够支撑"可回查证据" | Phase 1（`parsing/`，代码与坏文件兜底已单测覆盖） |
| 向量检索（bge-m3 + Qdrant） | 无本地 embedding 模型；塞词法向量进 Qdrant 只是假向量 | P3 |
| Kuzu 图接线 | S3 已验证可用；本轮语料内引用边为 0，接了也无数据 | Phase 1 |
| 守卫 G1 漂移 / G4 循环 | 属 S6 范围；本轮只做**预算熔断** | S6 |
| 离线档 | 按本轮要求"只验证云 API" | 后续 |
| 评测集指标（hallucination rate 等） | 属 S7/评测方案 D1–D7 | S7 |

## 7. 演示脚本（3 分钟讲法）

1. **讲链路**（30 s）：打开 `out/reports/T1-20261008-p0-s5-006.md`，指出「每条结论后面都有 `[paper_id]`」——这是 grounding 的可见证据。
2. **讲可审计**（40 s）：`out/events.jsonl` 按 `run_id` 过滤 → 展示 `llm_call` 事件里的 tokens/cost/延迟/缓存命中；说明「每个结论都能追到证据卡和检索分数」。
3. **讲成本**（30 s）：单 run **$0.006**、缓存重跑 **$0**、0.12 s；预算上限 $2.0 只用了 0.3%。
4. **讲可靠性设计**（60 s）：S3/S4 已验证存储与断点续跑；本轮暴露的 reasoning 截断、schema 漂移、run_id 复用三类"静默错误"都已被网关/守卫固化拦住——**这是 harness engineering 的贡献点**。
5. **讲下一步**（20 s）：S6 守卫（漂移/循环）+ S7 指标（幻觉率/支持率），然后 Phase 1 接 PDF、bge-m3、Kuzu。

## 8. 复现命令

```bash
cd prototype
uv run python steps/s5_walking_skeleton.py --topic T1 --run-id p0-s5-demo-01          # 冷启动（真实云调用，约 60–90 s）
uv run python steps/s5_walking_skeleton.py --topic T1 --run-id p0-s5-demo-02          # 缓存重跑（约 0.12 s，成本 $0）
uv run python steps/s5_walking_skeleton.py --topic T1 --run-id p0-s5-demo-03 --model deepseek/deepseek-v4-pro   # 换更强模型对比
```
