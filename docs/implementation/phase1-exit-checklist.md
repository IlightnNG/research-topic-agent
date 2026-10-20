# Phase 1.1 出口清单（Executable Exit Checklist）

> 规范依据：`phase1.1-scope-and-acceptance.md`（v1.1.1）§2 G1–G6、§7 D1–D10。
> 本文件只做一件事：**把"算完成"变成可跑的命令**。数字由命令生成，不手写。

---

## 0. 一键验收

```powershell
. .\scripts\env.ps1
uv run python scripts/verify_phase1.py --online --json docs/implementation/phase1-verify-report-online.json
```

- 退出码 `0` = 全部断言 PASS；`1` = 有红项（脚本会打印红绿表并落 JSON）。
- `--offline`：不联网（11 条）；`--online`：额外 2 条真实 arXiv 断言（13 条）。
- 临时目录默认 `D:/lit-agent-store/temp/verify-p1`，跑完自动清理；`--keep` 可保留现场。

## 1. 分层验收（对应 G1–G6）

| 层 | 命令 | 期望 |
|---|---|---|
| G1 测试 | `uv run pytest -q` | `230 passed`，0 failed |
| G2 静态 | `uv run ruff check .` | `All checks passed!` |
| G3 结构/schema | `uv run python scripts/check_structure.py`；`lit-agent db status` | `129/129`；schema `1.0`、24 表 |
| G4 离线全链路 | `verify_phase1.py --offline` | **11/11 PASS** |
| G5 真实数据全链路 | `verify_phase1.py --online` | **13/13 PASS** |
| G6 文档 | 本文件 + `phase1.1-known-gaps.md` + `adr/0006-*` + `RESULTS-P1.md` 定稿 | 四份存在 |

---

## 2. 断言清单（`scripts/verify_phase1.py`）

| # | 断言 | 判据 | 归属 |
|---|---|---|---|
| 1 | `structure` | 129/129 文件存在（src 包 + 根文件） | D1 |
| 2 | `schema` | `upgrade` 幂等；24 表；schema `1.0`；无缺表缺列 | D1 |
| 3 | `doctor` | 6/6 checks ok | G3 |
| 4 | `events` | 同 run 连发 3 事件 → `seq == [1,2,3]`（连续、不跳号） | D5 |
| 5 | `guards+budget` | 连续持平 → 停滞告警；超预算 → `stop` | D9 |
| 6 | `runner(offline)` | 四阶段 `intake→ingest→curate→report`；报告落库 | D7 |
| 7 | `idempotency` | 再跑一次：`papers` 不增、`report.content_sha` 相同 | D4 |
| 8 | `locks` | 同 topic 并发 → `E_LOCK_HELD`；结束后锁释放 | D9 |
| 9 | `stores` | `rebuild_graph + rebuild_vector` 后 `verify_counts.ok == True` | D6 |
| 10 | `metrics` | 有 claims 时 `grounding_rate` 非 `None`；`persist` 重复调用行数不增 | D7 |
| 11 | `api+sse` | health ok；未知 run → 404；chat → 501；SSE 以 `event: end` 收尾；OpenAPI ≥16 路径 | D7 |
| 12 | `e2e(online/arxiv)` | 真实抓取后 `papers>0`、claims 全带 citation、`degraded=False` | D7 |
| 13 | `stores(online)` | 真实数据重建后三方一致 `N/N/N` | D6 |

---

## 3. 基线结果（2026-10-20）

```
Offline: 11/11 PASS   （结构 129/129、schema 24 表、doctor 6/6、seq 1..3、锁 409、对账 2/2/2）
Online : 13/13 PASS   （真实 arXiv：papers=102、claims=50、cited=50、"102/102/102"）
```

落盘证据：
- `docs/implementation/phase1-verify-report.json`（离线）
- `docs/implementation/phase1-verify-report-online.json`（在线）
- `docs/implementation/phase1-doctor-snapshot.json`（结构快照）

---

## 4. 红绿表的使用规则

1. **只修红项**：红项按 `phase1.1-scope-and-acceptance.md` §4 分级，只有 P0 在 Phase 1.1 修。
2. **红项必须登记**：修不了或不该修的，写进 `phase1.1-known-gaps.md` 并标注归属阶段。
3. **不接受"手工验证通过"**：任何"完成"结论都必须来自本文件的命令输出。
4. **每步收尾都跑一次**：F2–F10 每步结束跑 `--offline`；涉及真实数据的步骤跑 `--online`。

---

## 5. F1 期间发现并修正的验证器问题（记录在案）

| 问题 | 性质 | 处理 |
|---|---|---|
| `structure.ROOT` 不存在 | 验证器写错（业务代码无误） | 改用 `structure.missing_files()` + 本地 root |
| `doctor.run_checks` 不存在 | 验证器写错 | 改用 `run_doctor()` |
| 事件断言未建 run 行 → `E_UNEXPECTED` | 验证器前置条件缺失 | 先 `jobs.start()` 再 emit，收尾 `ABORTED` |
| 在线对账未先重建 → `2 != 102` | 验证器顺序错误（D6 定义是"可重建后对账"） | 对账前先 `rebuild_*` |

> 四项全部属于**验证器自身**，没有改动任何业务代码——符合 F1"禁止改业务代码"的约束。
