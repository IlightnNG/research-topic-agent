# TODO

> 版本：2.0（2026-10-31）
> 管理规则见 `docs/CONVENTIONS.md` §5。
> 每个 TODO 只属于一个模块；完成后保留。

---

## 1. 索引

| ID | Module | Phase | Priority | Status | Title |
|---|---|---|---|---|---|
| TODO-001 | M3 | M3-P01 | P0 | done | Claim 类型校验与作者列表过滤 |
| TODO-002 | M3 | M3-P01 | P0 | done | Claim purity 真计算 |
| TODO-003 | M4 | M4-P01 | P0 | done | 全报告 claim 计数一致 |
| TODO-004 | M4 | M4-P01 | P0 | done | Paper Index metadata 完整 |
| TODO-005 | M4 | M4-P01 | P0 | done | 正文真实 claim 覆盖，禁止 ledger 刷分 |
| TODO-006 | M4 | M4-P01 | P0 | done | 动态方向质量 / min size / max share |
| TODO-007 | M4 | M4-P02 | P1 | done | 分方向 LLM writer |
| TODO-008 | M5 | M5-P01 | P1 | open | 模块分 + 方向分评分卡 |
| TODO-009 | M5 | M5-P02 | P1 | open | 100 篇 gold + LLM judge |
| TODO-010 | M2 | M2-P01 | P1 | open | 全文率 ≥30%（10 篇 3/10，100 篇待复跑） |
| TODO-011 | M1 | M1-P01 | P1 | done | Kernel ReAct + step checkpoint |
| TODO-012 | M6 | M6-P01 | P2 | open | 生产 UI / 错误格式 |
| TODO-013 | M1 | M1-P02 | P1 | open | 事件单写者与 module/severity |
| TODO-014 | M5 | M5-P03 | P2 | open | 自动调参闭环 |
| TODO-015 | M4 | M4-P02 | P1 | done | 分方向实时 section 流 |

---

## 2. 详情

### TODO-001 · Claim 类型校验与作者列表过滤

- Module：M3
- Phase：M3-P01
- Priority：P0
- Status：done
- Evidence：
  - `Tongxin Yuan, Zhiwei He, ...` 被当 claim；
  - `Faria Huq, ...` 被当 claim；
  - `claim.purity = 1.0`。
- Acceptance：
  - 作者列表、机构、references、致谢、版权全部拒绝；
  - 截断句拒绝；
  - 每条 claim 有 type；
  - fixture 覆盖 6 类负样本。
- Links：`docs/modules/m3-evidence/README.md`

### TODO-002 · Claim purity 真计算

- Module：M3
- Phase：M3-P01
- Priority：P0
- Evidence：当前 `research_claims += 1` 与 `claims += 1` 同步，purity 恒 1。
- Acceptance：
  - research/non-research 分开计数；
  - purity 可复算；
  - 负样本 purity < 1；
  - 指标落库。
- Links：`docs/modules/m3-evidence/README.md`

### TODO-003 · 全报告 claim 计数一致

- Module：M4
- Phase：M4-P01
- Priority：P0
- Evidence：概述 185；D1/D2/D3 各 6；ledger 只到 C103。
- Acceptance：
  - overview = sections = matrix = ledger；
  - 不一致 verifier reject；
  - 测试覆盖 mismatch。
- Links：`docs/modules/m4-report/README.md`

### TODO-004 · Paper Index metadata 完整

- Module：M4
- Phase：M4-P01
- Priority：P0
- Evidence：`| W... | W... |`，无标题/作者/venue。
- Acceptance：
  - index 含 title/authors/venue/year/url；
  - metadata 缺失论文标记；
  - 测试覆盖。
- Links：`docs/modules/m4-report/README.md`

### TODO-005 · 正文真实 claim 覆盖

- Module：M4
- Phase：M4-P01
- Priority：P0
- Evidence：86 篇只写 6 条；ledger 刷 coverage=1。
- Acceptance：
  - `report.claim_coverage` 只算正文实际引用；
  - 每方向正文覆盖 ≥0.8；
  - ledger/index 不计 coverage。
- Links：`docs/modules/m4-report/README.md`

### TODO-006 · 方向质量

- Module：M4
- Phase：M4-P01
- Priority：P0
- Evidence：3 方向；max_share 0.86；`Agents / Wang`。
- Acceptance：
  - 动态方向数；
  - min size ≥3；
  - max_share ≤0.6；
  - 禁止作者/venue 名；
  - 不达标 → degraded。
- Links：`docs/modules/m4-report/README.md`

### TODO-007 · 分方向 LLM writer

- Module：M4
- Phase：M4-P02
- Priority：P1
- Evidence：writer 是确定性模板；open questions 全相同；differences 不可比。
- Acceptance：
  - 每方向 EvidencePack；
  - LLM 写 section；
  - code gate + verifier；
  - 失败只重写该 section；
  - 与模板对比审计。
- Links：`docs/modules/m4-report/README.md`

### TODO-008 · 模块分 + 方向分评分卡

- Module：M5
- Phase：M5-P01
- Priority：P1
- Evidence：当前 score = 0.5×F1 + 0.3×citation + 0.2×字数；字数进入评分。
- Acceptance：
  - 模块权重；
  - 方向分；
  - 硬门禁；
  - confidence；
  - 字数只做 gate。
- Links：`docs/modules/m5-evaluation/README.md`

### TODO-009 · 100 篇 gold + LLM judge

- Module：M5
- Phase：M5-P02
- Priority：P1
- Evidence：只有 20 篇 silver；无 judge。
- Acceptance：
  - 3×100 金标；
  - double annotation；
  - judge 校准；
  - 数据集 hash 冻结。
- Links：`docs/modules/m5-evaluation/README.md`

### TODO-010 · 全文率 ≥30%

- Module：M2
- Phase：M2-P01
- Priority：P1
- Evidence：100 篇只有 5 篇全文。
- Acceptance：
  - 多源 PDF/HTML；
  - fulltext ratio ≥0.3；
  - abstract-only 明示；
  - 失败降级记录。
- Links：`docs/modules/m2-source/README.md`

### TODO-011 · Kernel ReAct + step checkpoint

- Module：M1
- Phase：M1-P01
- Priority：P1
- Evidence：minimal action loop；仅 Node 边界 pause。
- Acceptance：
  - LLM completer；
  - step checkpoint；
  - no-progress；
  - cost；
  - token/step 事件。
- Links：`docs/modules/m1-engine/README.md`

### TODO-012 · 生产 UI / 错误格式

- Module：M6
- Phase：M6-P01
- Priority：P2
- Evidence：只有最小 timeline；错误未统一。
- Acceptance：
  - 新 timeline；
  - 错误响应；
  - SSE replay；
  - e2e。
- Links：`docs/modules/m6-interface/README.md`

### TODO-013 · 事件单写者

- Module：M1
- Phase：M1-P02
- Priority：P1
- Evidence：EventLog 用 MAX(seq)+1，并发可能冲突。
- Acceptance：
  - 单写者/allocator；
  - seq 连续；
  - 并发测试。
- Links：`docs/LOGGING.md`

### TODO-014 · 自动调参闭环

- Module：M5
- Phase：M5-P03
- Priority：P2
- Evidence：Tuner 有，但只有 20 篇 silver；阈值无差异。
- Acceptance：
  - 参数网格；
  - Pareto；
  - experiments；
  - 硬指标回退拒绝；
  - 可复跑。
- Links：`docs/modules/m5-evaluation/README.md`

### TODO-015 · 分方向实时 section 流

- Module：M4
- Phase：M4-P02
- Priority：P1
- Evidence：当前 section 生成后 emit；writer 仍整篇构造。
- Acceptance：
  - 每 section 生成即 emit；
  - SSE 可见；
  - 失败 section 单独重试。
- Links：`docs/modules/m4-report/README.md`

---

## 3. 已完成

| ID | 内容 | 日期 |
|---|---|---|
| — | v2 独立包 | 2026-10-31 |
| — | 旧代码/文档移出仓库 | 2026-10-31 |
| — | OpenAlex/PDF/100 篇真实联调 | 2026-10-31 |
