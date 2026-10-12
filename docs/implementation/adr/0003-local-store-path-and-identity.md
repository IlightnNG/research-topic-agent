# ADR 0003: 本地存储的路径形态、生命周期与"库身份"校验

Status: accepted（Phase 0 实测后冻结；Phase 1 部署形态待二次决策）
Date: 2026-10-09
Context（三条实测约束，都会静默出错）
1. **路径形态不同**：Kuzu 的 `kuzu_path` 是**单文件**，Qdrant local 的 `qdrant_path` 是**目录**。
   早期清理代码用 `shutil.rmtree(path, ignore_errors=True)`，对文件抛 `NotADirectoryError` 被
   `ignore_errors` **静默吞掉** → 旧库未删 → `MERGE` 跨运行累积节点（症状：`expected_authors=631 / actual=957`，
   差集"只多不少"）。
2. **落盘时机**：Kuzu **只在 `Database.close()` 时 checkpoint**（`Connection.close()` 不触发）：
   导入 300 篇后文件 0.004 MB → `conn.close()` 仍 0.004 MB → `db.close()` 后 2.426 MB。
   关闭前统计磁盘会读到 0.0 MB 假值。
3. **非 ASCII 路径**：Windows 上 Kuzu 打不开含非 ASCII 的路径（`IO exception: Cannot open file … Error 3`）；
   开发机仓库路径是 `E:\大学\…`，故 `kuzu_path` 指向纯 ASCII 目录（`E:\lit-agent-data\kuzu`）。
4. 另加一条来自 S5 的同类问题：`CREATE TABLE IF NOT EXISTS` **不会修正已存在的旧结构**
   （S3 spike 的 `papers` 表缺列 → 启动即 `no column named abstract`）。

Decision:
1. 存储清理统一走 `reset_store_path(path)`：**文件/目录都能清**，并顺带清 `.wal/.lock/.shm` 同级文件。
2. 磁盘统计统一走 `path_size_mb(path)`（文件按自身大小、目录递归），且**必须在关闭 DB 句柄之后**调用。
3. **导入前空库哨兵**：`store_is_empty()` 断言目标库为空，非空即报 `E_STORE_NOT_EMPTY`（防"旧库残留"被误判为本次结果）。
4. **库身份校验**：`SqliteStore` 启动时比对必须存在的列（`REQUIRED_COLUMNS`），不一致抛
   `StoreSchemaError` → 事件 `E_STORE_SCHEMA_MISMATCH`，并只允许通过**显式** `reset=True` / `--reset-store` 重建。
5. **部署路径规范化**：生产/部署环境的数据目录必须是**纯 ASCII 路径**；`pdf`/`sqlite` 无此限制。
6. Qdrant **local（嵌入式）模式无 ANN 索引**（`local_collection.py` 中 `HNSW` 出现 0 次，纯 Python 逐点扫描 +
   Python 层 payload 过滤；`create_payload_index` 直接告警无效）→ 向量检索的**部署形态**需在 Phase 1 三选一：
   **A** 接受 local 暴力扫描（≈0.038 ms/点，2 万篇 ≈0.76 s/查询，但**精确 kNN、召回更高**）／
   **B** 起本地 Qdrant server 进程（HNSW + payload 索引 + 量化，**会改动架构 §8「无外部服务依赖」**）／
   **C** 换嵌入式 ANN 库（hnswlib/FAISS/LanceDB，需自实现过滤与持久化）。

Impact:
- 契约/部署：`implementation-guide.md` §1.3 配置（`kuzu_path` 单文件 + ASCII 约束）、
  §2.6/§2.7 存储 DDL 与"建库前置检查"；`architecture-overview.md` §8（部署形态）。
- 受影响模块：`stores/`（三库初始化与校验）、`runtime/`（启动自检）、部署脚本。
- 测试：`tests/test_stores.py`（schema 守卫、reset 重建、幂等零增长、计数对账）。

Migration:
- Phase 0：已在 `steps/s3_storage_spike.py` 与 `lit_agent_min/stores.py` 落地；
  开发机 `config.local.yaml` 的 `kuzu_path` 指向 `E:\lit-agent-data\kuzu`。
- Phase 1：把 `reset_store_path` / `path_size_mb` / `store_is_empty` / `REQUIRED_COLUMNS` 迁入
  `stores/` 并在启动自检中调用；数据目录迁到纯 ASCII 路径。

Verification:
```bash
uv run python steps/s3_storage_spike.py --papers 5000     # 幂等/重建/磁盘/单写者
uv run pytest -q tests/test_stores.py                     # schema 守卫 + 计数对账
```
