# ADR 0001: `Paper.merged_ids` 与 `paper_merges` 表（去重合并关系入契约）

Status: accepted（Phase 0 实测后冻结，Phase 1 实现）
Date: 2026-10-09
Context:
- S1b 实测：同一论文的多版本记录占比 **19.3–19.8%**（version copies 101/93），去重是必需环节。
- D6 设计（`design/agent-design-decisions.md` F6/F7、`sources/normalize.py`）要求"三段式去重
  （精确键 → 指纹 → 模糊确认）"并**保留合并关系**：主记录与 `merged_ids` 都不删除，
  以便引用回查、评测复现与人工审计。
- S5 实测：现有冻结契约 `Paper`（`implementation-guide.md` §2.3）**没有** `merged_ids` 字段，
  因此 Phase 0 只能把合并关系放在去重结果对象里、落到 SQLite 的 `paper_merges` 表
  （`lit_agent_min/stores.py`），**报告与检索都用不到它** —— 这是契约缺口。

Decision:
1. `Paper` 增加字段：`merged_ids: list[str] = []`（被合并到本记录的其他 canonical id，去重后保留溯源）。
2. 冻结表结构新增（Phase 1 SQLite/Alembic 迁移）：
   ```sql
   CREATE TABLE paper_merges(
       primary_id TEXT NOT NULL,
       merged_id  TEXT NOT NULL,
       run_id     TEXT,
       reason     TEXT,          -- 命中哪一段：exact_id | fingerprint | fuzzy
       PRIMARY KEY(primary_id, merged_id)
   );
   ```
3. 去重**不得删除任何原始记录**：源记录原样入库（`papers_raw` / 事件 payload），合并只影响"对外可见的主记录"。
4. 主记录选择必须**确定性**（`models.Paper` 排序键：有摘要 > 有 DOI > 作者多 > id 字典序），
   保证"同输入同主记录"，从而保证重跑幂等与指标可复算。

Impact:
- 契约：`models.Paper`（新增可选字段，向后兼容）；`implementation-guide.md` §2.3 需同步；表结构 +1。
- 受影响模块：`sources/normalize.py`（去重）、`stores/`（写入）、`eval/metrics.py`（去重率指标）、
  报告脚注（披露合并数量）。
- 测试：`tests/test_normalize.py`（已有 14 例，含同 id 重复行与版本副本两类）；
  Phase 1 需补"合并关系可回查"的集成测试。

Migration:
- Phase 0（已完成，无需迁移）：合并关系存 `paper_merges` 表；`Paper` 无字段。
- Phase 1：加 `Paper.merged_ids`；写 Alembic 迁移把 `paper_merges` 的既有行回填到 `papers.merged_ids`
  （或保留表作为审计源、字段作为读优化）。

Verification:
```bash
uv run pytest -q tests/test_normalize.py            # 去重与主记录选择
uv run python steps/s5_walking_skeleton.py --topic T1 --run-id p0-s5-adr1   # 重跑：papers_new_this_run=0
```
