# Phase 0 决策门材料（一页纸 + 5 分钟 demo）

> 用途：**导师/组会决策门**。目标：用一页数字说明"选型可行、闭环跑通、风险已知"，请求进入 Phase 1。
> 配套详版：`prototype/RESULTS.md`（定稿台账，§0 一页摘要 / §4 静默错误清单 / §5 决策门结论）。
> 全部数字均可复现：`cd prototype &&` 见表内命令；证据文件在 `prototype/out/`。

---

## 一、一页数字（Phase 0 = Step 0–7 全部完成，S2 本轮豁免）

| 维度 | 结论 | 关键数字 |
|---|---|---|
| **数据源** | OpenAlex 为主 + arXiv 补时效；**白名单过滤是主通道** | 白名单 3 年 **386 篇**（≈129/年，下限）；arXiv 收录率 **91.7%**；白名单↔宽召回 Jaccard **0.004–0.014**；重复率 **19.3–19.8%** |
| **存储** | **三库方案成立，不需换 Neo4j/Milvus** | 图 2-hop p95 **4.42 ms**；幂等零增长；删库重建计数一致；磁盘 **64.9 MB/5k**；⚠️ 向量 p95 **155 ms**（目标 100 ms，**已归因**：Qdrant local 无 ANN） |
| **编排** | LangGraph 断点续跑可用；**恢复粒度 = 节点边界** | 3 次硬杀全部恢复；`invoke(None)` 后状态与不中断对照**逐字段一致**；checkpoint 仅 **4 KB/超级步** |
| **闭环（S5）** | **真实云 LLM 端到端跑通** | 报告 **8.9k–10.8k 字 / 16–23 claims / 100% 带可回查引用**；冷启动 **$0.0036–0.0126**（60–91 s）；缓存重跑 **$0 / 0.08 s** |
| **守卫（S6）** | 三守卫 + 预算看门狗达标 | 5 类注入 ×3 次 **检出率 1.00**；正常 run **误报 0**；G1 阈值按分布标定 0.0777/0.0867 |
| **指标（S7）** | 5 指标可从**事件**算出并可手工复算 | grounding **0.7949**、幻觉率 **0.2051**、注入 TPR **1.0**、FPR **0**、成本均值 **$0.006294**/run |
| **工程质量** | 累计抓出 **12 个"静默错误"** 并固化为代码/守卫/ADR | 新增 **3 份 ADR**；设计台账 71 条；测试 **112 项通过**；ruff 干净 |

**成本画像**：单 run 闭环 **<$0.013**（冷启动）/ **$0**（缓存）；周更 52 周 × 3 topic 也仅约 **$1/年**量级（按本轮实测单价外推）。
**规模画像**：Kuzu 导入 34 ms/篇（2 万篇 ≈11 min，Phase 1 改 `COPY FROM`）；向量检索 0.038 ms/点（2 万篇 ≈0.76 s/查询）。

---

## 二、5 分钟 demo 脚本（两条命令）

```bash
cd prototype

# ① 闭环（40 秒：缓存命中，不花钱；去掉 --no-cache 前的冷启动约 60–90 s）
uv run python steps/s5_walking_skeleton.py --topic T1 --run-id p0-demo-01
#   → out/reports/T1-<date>-p0-demo-01.md   报告（每条结论带 [paper_id]，可回查）

# ② 守卫注入（3 秒，离线）：6 场景 × 3 次完整矩阵
uv run python steps/s6_guards_demo.py --inject all --repeats 3
#   → 注入检出率 1.00（5 类各 3/3）、正常 run 误报 0/3；
#     其中 loop：首次 replan → 再次 abort（6 步内终止，不空转烧预算）
#   （只想看单场景：--inject loop --repeats 3；注意此时矩阵里没有正常对照，FPR 会显示 0/0）

# ③ 指标（1 秒）
uv run python steps/s7_metrics.py --include-run p0-s5-cold
#   → out/metrics_report.md（5 指标 + 守卫有效性 + 口径警示）
```

**讲解要点（每点一句话）**
1. **闭环**：打开报告，指出"每条结论后面都有 `[paper_id]`"——引用由脚本强制回查，回查不到就丢弃并计数（`dropped=0`）。
2. **可审计**：`out/events.jsonl` 按 `run_id` 过滤 → 展示 `llm_call` 事件的 tokens/cost/延迟/是否命中缓存；`out/llm_cache/` 让重跑**确定且免费**。
3. **可自纠错**：`--inject loop` 的事件链 `tool_call → guard_trigger{replan} → recovery{恢复包} → guard_trigger{abort} → metric`，处置按升级阶梯执行。
4. **可量化**：`metrics_report.md` 一页给出 grounding / 幻觉率 / 检出率 / 误报率 / 成本时延；**手工抽查过**（事件侧与 claims 文件完全一致）。
5. **工程性**（本项目的真正贡献点）：12 个"不报错但结论错"的静默错误被实测抓出并固化——例如 reasoning 模型截断导致空正文、`run_id` 复用导致事件合并、阈值口径错配导致守卫全误报。

---

## 三、待确认 / 待决策（请求导师意见）

| # | 事项 | 建议 | 影响 |
|---|---|---|---|
| 1 | **是否进入 Phase 1**（P1 骨架 + P2 harness） | **建议进入**：出口清单除"导师确认"外全绿 | 决定后续排期 |
| 2 | **向量检索部署形态三选一** | Phase 1 第一周决策：**A** 接受 local 暴力扫描（改验收目标）/ **B** 起本地 Qdrant server 进程（**改动"无外部服务依赖"表述**）/ **C** 换嵌入式 ANN 库（hnswlib/FAISS/LanceDB） | 影响部署形态与架构 §8 |
| 3 | 测试 topic 集与评测周数 | Phase 1 起 3–5 topic × ≥4 周周更 | 决定评测 campaign 规模 |
| 4 | 前端框架（Vue3 / React） | 倾向 Vue3 + Vite + ECharts（与选型文档一致） | P5 排期 |
| 5 | grounding 口径升级 | Phase 1 建 **D2 gold 事实集 + 异源 judge**，才能报 §5.1 的忠实度 | 当前 grounding/幻觉率是**模型自报标签**，不能当论文结论 |
| 6 | 是否恢复本地模型档（S2） | 维持本轮豁免（云-only） | 影响成本与隐私档位 |

---

## 四、Phase 1 首批 backlog（按优先级）

1. **向量部署形态决策** → `stores/vector.py`（A/B/C）
2. `Paper.merged_ids` + `paper_merges` 迁移（ADR-0001）
3. Kuzu 首次全量导入改 **`COPY FROM`**（2 万篇压到分钟级）
4. **PDF 全文** + `parsing/`（PyMuPDF → pdfplumber 兜底已实现且有坏文件单测）
5. `cited_by` **反向构边** + 引用覆盖率指标（目标：白名单 ≥60% 有入边）
6. 事件落 SQLite **`run_events`**（ADR-0002：payload JSON + kind 索引）
7. **启动自检**：空库哨兵 + schema 身份校验 + 纯 ASCII 数据目录（ADR-0003）
8. **D2 gold 事实集 + 独立 judge**（把 grounding 从"自报"升级为"核验"）
9. 补测删除/更新路径、崩溃一致性、同进程并发（S3 §2.10 的覆盖边界）
10. UI（Topic / Report / Chat）与周更调度（P4/P5）

---

## 五、诚实边界（Phase 0 未做/未验证）

调度与周更（APScheduler）、三套 UI、多 agent 角色拆分、完整守卫 G2/G3/G5–G13、
恢复包 A/B 有效性对比、**真实故障注入**（本轮为确定性模拟）、PDF 全文解析、bge-m3 向量、
跨主题泛化（仅 T1 实测）、本地模型档（S2 豁免）。
