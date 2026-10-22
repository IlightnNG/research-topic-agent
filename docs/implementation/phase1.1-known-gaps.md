# Phase 1.1 缺口登记册（Known Gaps）

> 规范依据：`phase1.1-scope-and-acceptance.md`（v1.1.1）§4 分级、§5 登记册。
> **纪律**：发现 ≠ 立刻改。新问题先在此登记（级别 + 归属阶段），再按批次处理。
> 本文件是"什么不修、为什么不修、什么时候修"的唯一凭据。

## 1. 分级定义（复述）

| 级别 | 含义 | Phase 1.1 处置 |
|---|---|---|
| **P0** | 出口断言红 / 数据错误 / 违反契约 | 必须修 |
| **P1** | 有 workaround，影响体验不影响结论 | 步骤内选做 |
| **P2** | 未实现功能、性能、美化、重构 | 一律延后 |

## 2. 已关闭（Phase 1.1 期间修复并验证）

| ID | 缺口 | 修复 | 证据 |
|---|---|---|---|
| G-01 | `upsert_many` 不写 authors → 真实数据 `authors=0` | F2：同事务写 `authors` + `paper_authors`（幂等） | `verify --online`：`authors=556 links=564`；`test_author_persistence` 3 例 |
| G-06 | 无 `E_NOT_FOUND`，404 借用 `E_CONFIG_INVALID` | F3：新增码 + 404/400 语义分离 + 补全 24 个 retryable 映射 | `test_errors` 全码覆盖；`/api/runs/nope`→404 `E_NOT_FOUND` |
| G-07 | `sources sync` 无 CLI 契约测试 | F4：`--topic/--limit` + 单源语义 + 3 例契约测试 | `test_sync_cli` 3 例 |
| G-14 | SSE 断线重连未测 | F7：分页/Last-Event-ID/重连/越界/409 共 5 例 | `test_sse_contract` 5 例 |
| — | 报告 claims 未落表 → 指标 `claims=0`（F5 期间发现） | F5：`_persist_claims` 同事务写 claims/citations | `test_report_metrics_alignment` 3 例；`metrics claims=4` |

## 3. 仍开放（按归属阶段）

| ID | 缺口 | 级别 | 归属 | 说明 / 为什么不现在做 |
|---|---|---|---|---|
| G-02 | guide §3.6 差异登记未逐条回写、ADR 索引未补 0004/0005 链接 | P1 | F8/F9 收口 | 差异已在 §4 汇总；逐条回写属文档整理，不影响判据 |
| G-03 | ~~缺 ADR-0006~~ | ~~P1~~ | **已关闭 2026-10-20** | 见 `adr/0006-event-and-schema-format-freeze.md` |
| G-04 | 前端无 TS / 无 Element Plus / 单文件三页签 | P2 | **Phase 1.2**（Vue 3） | 不影响功能；用户已确认后置 |
| G-05 | ~~无浏览器 e2e~~ | ~~P2~~ **已关闭 2026-10-21** | Phase 1.2 ✅ | Playwright 5 例（`npm run test:e2e`） |
| G-08 | 单源同步（openalex 优先，否则取一个），无多源合并 | P2 | P4 | 需先定合并口径（同一论文多源字段取舍） |
| G-09 | `config/seeds/topics.yaml` 的 `venue_ids` 未解析 | P2 | P4 | arXiv 路径可绕过；OpenAlex 需 key |
| G-10 | 12 个骨架模块（agents×5、eval×4、breaker、mcp_adapter、paper_pdf） | P2 | P2–P5 | 设计上的显式未实现，调用即 `E_FEATURE_DISABLED` |
| G-11 | `gateway/breaker.py` 熔断未实现 | P2 | P2 | 无 key 时无实际调用，先做无意义 |
| G-12 | run 同步执行（未异步 + 202） | P2 | P2 | 已有 409 阻塞语义，UI 可用 |
| G-13 | `phase2-implementation-steps.md` 不存在 | P1 | F9 | 本阶段末产出首版（含出口标准，不写实现） |
| G-17 | F5/F7/F8/F9 仅有手动验证（无 e2e 用例） | P1 | 1.2.x | 见 `phase1.2-frontend-spec.md` §15.4 |
| G-18 | ~~`sections[]` 仍是 claims 的派生~~ | ~~P2~~ **已关闭 2026-10-21** | Phase 2 S12 ✅ | `reports.sections_json` + 迁移 0003，按 claims 分组落库 |
| G-19 | ~~前端类型手写~~ | ~~P2~~ **已关闭 2026-10-21** | Phase 2 S12 ✅ | `scripts/gen_web_types.py` → `types.gen.ts`（6 schemas） |
| G-20 | 生产部署缺 history 路由回退（`try_files`） | P2 | 部署清单 | dev 由 Vite 兜底 |
| G-16 | 结构快照未纳入自动流程 | P1 | F8 ✅ | 已产出 `phase1-doctor-snapshot.json`；F10 复核时刷新 |

## 4. 已知偏差（实现 vs 计划的差异，非缺陷）

| 偏差 | 影响 | 记录位置 |
|---|---|---|
| 触发运行为同步执行（无 202） | 长任务会占住请求 | G-12 |
| `E_CONFIG_INVALID` 现为 400（原为 404） | 前端需按新语义处理 | F3 记录 |
| 报告为"机械折衷"（一卡一 claim），无 LLM 抽取 | 报告质量有限，但 grounding 真实 | §3.11 |
| 上下文注入未物化进事件（P3） | 同 run 重跑 prompt 可能不同 | §3.12 |
| 向量索引用 `HashingEmbedder` 于测试/验证 | 真实语义检索质量未验证 | ADR-0004 |

## 5. 如何新增一条

1. 写清：现象、复现命令、影响面（数据/契约/体验）、建议级别与归属阶段。
2. **先登记再做**；若判断为 P0，需同时更新 `phase1.1-scope-and-acceptance.md` §5 并立即排入当前批次。
3. 关闭时：在本文件 §2 追加一行（ID、修复步、证据命令/测试名），并在原表把该行划掉。
