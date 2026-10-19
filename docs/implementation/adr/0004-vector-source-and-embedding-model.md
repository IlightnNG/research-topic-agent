# ADR 0004: 向量检索的部署形态、嵌入模型与重嵌入流程

Status: **accepted**（Phase 1 Step 1.5 前置，2026-10-19）
Supersedes: 无（细化了 `implementation-guide.md` §2.6 未定的部分）
Relates: ADR-0003（存储路径与库身份）、ADR-0005（`store_meta` / `embeddings` 表）、
`design/agent-design-decisions.md` F8（缓存即可复现性来源）/ F9（阈值须按 scorer 分布标定）

---

## 1. Context（为什么必须决策）

1. **契约已经锁了维度，但没锁"谁产生向量"**：`implementation-guide.md` §2.6 冻结
   `papers` collection = `size=1024`、`distance=Cosine`、payload 六个字段；
   但 1024 维来自 bge-m3 的假设，**Phase 0 从未真正接入 embedding**（S3/S5 用的是词法打分与合成向量）。
   Phase 1 若不决策，1.5 会卡住，或实现者各自引入不同维度/不同模型，导致"重建对账一致"（D6）无法成立。
2. **Phase 0 的部署形态实测已给出事实**（出处 `../prototype/RESULTS.md` §2.9–2.10）：
   - Qdrant **local 模式是纯 Python 暴力扫描**，无 ANN：**0.038 ms/点**，top-10 p95 = **155 ms @5k**；
     纯算力只占 0.3%，74% 开销在 payload 过滤；线性外推 2 万点 ≈ **0.76 s/查询**。
   - 因此 P1 的 100 ms 目标与 local 形态**错配**（是目标问题，不是架构缺陷）。
   - 结论要求 Phase 1 显式三选一：A 接受 local 暴力（按形态重标定目标）／B 起本地 server（改架构"无外部服务"表述）／
     C 换嵌入式 ANN 库（保留单进程）。
3. **约束**（不可协商）：单机、**无 Docker / 无常驻服务进程**（guide §1.2 明令禁止）；
   云端**只用 DeepSeek**（其无 embedding 端点）；离线可复现；模型一次下载后可断网运行。
4. **语料特征**：学术论文**以英文为主**，领域为 **AI / 计算机 / 电子硬件 / 通信**（导师方向）；
   偶有中文作者的中文摘要或混合标题；摘要长度 ~1–2k 字符（≈300–800 tokens），全文分块后单块 ≈300–500 tokens。
5. **Phase 0 阈值是用词法分数标定的**（block 0.0777 / warn 0.0867，质心 0.0885 vs 0.0670），
   与 embedding 语义分数**不同量纲**；换真嵌入后必须重标定（F9），否则守卫会大面积误报/漏报。

---

## 2. Decision 总览

| # | 决策 | 一句话 |
|---|---|---|
| **D1** | **部署形态 = A：Qdrant local 嵌入式**（`data/qdrant` 目录，进程内，无 server） | 保持"零外部服务"，接受暴力检索；写死复评触发条件 |
| **D2** | **嵌入模型 = `BAAI/bge-m3`**（**1024 维**、多语、8192 ctx、MIT） | 与 §2.6 契约零冲突，英文强、能兜非英文 |
| **D3** | **备选模型 = `BAAI/bge-large-en-v1.5`**（同 1024 维、纯英文、约 1/2 算力） | 性能不足时热切换，**无需改契约** |
| **D4** | **推理栈 = `sentence-transformers`（torch CPU, fp32, 归一化）**，新增该依赖 | 确定性、无网络、Windows 可用 |
| **D5** | **缓存 = `embeddings` 表**（`text_sha+model_id+model_rev`） | 同文本永不重算；换模型不混用 |
| **D6** | **确定性约束**（线程数/种子/fp32/`eval()`）+ 同文本二次嵌入 cosine ≥ 0.9999 | 保证 D4"重跑幂等"与 D6"重建一致" |
| **D7** | **身份校验**：`model.get_dimension() == store_meta.dim == collection.size == 1024` | 不匹配即 `E_VECTOR_DIM_MISMATCH` / `E_VECTOR_MODEL_MISMATCH` |
| **D8** | **换模型 = 新 collection + 全量重嵌入 + 指针切换**（`active_collection`） | **禁止原地覆盖** |
| **D9** | **阈值重标定是换模型的强制后续**（P2 的 `P2-GUARD-02`） | 不重标定不得启用 drift 守卫 |
| **D10** | **不做** ANN/量化/GPU/云端 embedding（P1 范围内） | 触发条件见 §9 |

---

## 3. D1：部署形态选 A（Qdrant local）

### 3.1 三选一的裁决

| 方案 | 内容 | 裁决 | 理由 |
|---|---|---|---|
| **A** | Qdrant **local**（嵌入式，`path=data/qdrant`） | ✅ **采纳** | 零外部进程、零运维、Phase 0 已验证写入/过滤/幂等；P1 规模 ≤2 万点下 p95 ≈0.76 s，而向量检索在 P1 仅用于**离线批处理**（守卫打分、证据重排），不在交互首屏 |
| B | 本地 Qdrant **server**（Docker/进程 + HNSW） | ❌ 不采纳 | 违反 guide §1.2"禁止 Docker/外部服务"；需改架构 §8 表述；单机单人项目运维成本无收益 |
| C | 换嵌入式 ANN 库（hnswlib / usearch / faiss） | ❌ P1 不采纳 | 三者都要**自己实现 payload 过滤与持久化**（Phase 0 实测过滤占 74% 开销，正是难点）；`sqlite-vec` 过滤能力弱；Chroma/LanceDB 引入新依赖与原生二进制。留作 §9 的复评选项 |

### 3.2 复评触发条件（写死，达到即开新 ADR）

| 条件 | 阈值 | 动作 |
|---|---|---|
| 规模 | `papers` 点数 > **50,000**（或 `chunks` 启用后 > **200,000**） | 重新评估 A/B/C |
| 延迟 | 单次 top-10 查询 p95 > **500 ms**（连续 3 次 run 的实测） | 同上 |
| 功能 | 需要 ANN / 量化 / 多租户分片 | 同上 |
| 交互 | 向量检索进入**用户同步等待路径**（如 Chat 首屏） | 补充"预计算 + 缓存"方案后再评估 |

> 复评不是"想换就换"：必须带实测数据（点数、p95、内存）出 ADR，否则 A 保持不变。

### 3.3 形态约束（落地细节）

- `qdrant_path` 是**目录**（与 Kuzu 的"单文件"不同，ADR-0003 §1）；用 `QdrantClient(path=...)` **嵌入式**模式。
- 同一进程内**只允许一个 client 实例**（local 模式有目录锁）；统一走 `stores/vector.py` 的 `get_client()` 单例。
- `close()` 前必须 `flush`，磁盘统计在 close 后测量（ADR-0003 §2 的同一条纪律）。
- collection 名带版本：`papers_v1`（换模型 → `papers_v2`），当前活跃名记在 `store_meta.active_collection`。
- **逻辑名与物理名**：契约（§2.6）里的 `papers` 是**逻辑集合名**；物理 collection 由 `active_collection` 指定。
  代码**只允许**通过 `store_meta.active_collection` 解析，**禁止**在业务代码里硬编码 `"papers"` / `"papers_v1"`。

---

## 4. D2/D3：模型选择

### 4.1 主选：`BAAI/bge-m3`

| 属性 | 取值 | 与项目的契合点 |
|---|---|---|
| 维度 | **1024** | 与 §2.6 冻结契约**完全一致**，零契约变更、零迁移 |
| 参数/体积 | 568M / ≈**2.27 GB**（fp32 权重） | 单机磁盘可接受（Phase 0 数据盘 65 MB/5k，模型是最大单项） |
| 上下文 | **8192 tokens** | 摘要（300–800 tokens）与 500-token 分块都不截断 |
| 语言 | 多语（100+） | 英文为主的论文最优；偶发中文标题/摘要不至于退化 |
| 许可 | **MIT** | 论文可发表、代码可开源 |
| 检索表现 | MTEB 多语检索第一梯队；支持 dense / sparse / colbert 三种输出 | dense 就够用；sparse 可选作 P3 混合检索（另开 ADR） |
| 查询前缀 | **不需要** instruction 前缀 | 调用侧简单，不易写错 |
| 运行 | `sentence-transformers` 直接支持（无需 remote code） | 离线、确定性、Windows 友好 |

### 4.2 备选：`BAAI/bge-large-en-v1.5`（同维度热切换）

| 属性 | 取值 | 何时切 |
|---|---|---|
| 维度 | **1024** | 契约不变 |
| 参数/体积 | 335M / ≈**1.34 GB** | 批处理耗时不可接受、或内存紧张时 |
| 上下文 | 512 tokens | 摘要够用；分块预算必须 ≤512（当前 300–500，兼容） |
| 语言 | 纯英文 | 语料以英文为主时无损失；出现中文摘要会明显退化 |
| 查询前缀 | **需要**：`Represent this sentence for searching relevant passages: ` | 必须写进 `gateway/policy` 的 embed 配置，不许散落在调用点 |

**切换成本**：改 `store_meta` → 新建 `papers_v2` → 全量重嵌入（走缓存，旧缓存按 `model_id` 不复用）→
对账 → 切指针 → 删旧 collection → **重标定阈值**（§8）。代码不改，只改配置。

### 4.3 明确不选（写清理由，避免后续重复讨论）

| 候选 | 不选理由 |
|---|---|
| OpenAI `text-embedding-3-*` / 任何云端 embedding API | 违背"云端只用 DeepSeek"；破坏离线可复现；引入第二家供应与密钥 |
| `nomic-embed-text-v1.5`（768 维） | 维度不符契约（需改 §2.6 + 全量重建）；上下文与英文表现并不优于 bge-m3 |
| `intfloat/multilingual-e5-large`（1024 维） | 可用，但需 `query:`/`passage:` 前缀且英文检索略逊 bge-m3；作为第三备选 |
| `jina-embeddings-v3`（1024 维） | 许可 **CC-BY-NC-4.0**（非商用）风险；需 `trust_remote_code` |
| `BAAI/bge-small-en-v1.5`（384 维） | 维度不符；且 P1 不追求极致速度（离线批处理） |
| 自训练/微调 embedding | 超出硕士项目范围；无标注检索集 |

---

## 5. D4：推理栈与依赖

### 5.1 依赖变更（本 ADR 授权，guide §1.2 之外）

```toml
# pyproject.toml（新增）
dependencies = [
  "sentence-transformers>=3.0",   # 内含 torch CPU、transformers、tokenizers
  "numpy>=1.26",                  # 归一化与 vec BLOB 编解码（qdrant-client 亦依赖）
]
```

| 影响 | 说明 |
|---|---|
| 安装体积 | Windows CPU wheel ≈ +600 MB（torch 最大项）；`uv sync` 首次耗时明显增加 |
| 首次运行 | 模型下载 ≈2.27 GB（`HF_HOME` 可指向 `data/models/`，**须 ASCII 路径**） |
| 离线 | 下载一次后 `HF_HUB_OFFLINE=1` 可完全断网运行；CI/测试用**假编码器**（见 §7.3），不下载模型 |
| 版本锁定 | `uv.lock` 锁死；`model_rev` 另记模型 commit（§6.2） |

> **为什么不放 optional extra**：P3 的上下文折叠与证据重排都依赖同一编码器；做成可选会让"测试通过但线上缺依赖"。
> 体积代价由 ADR 显式承担。

### 5.2 调用形态（唯一允许的实现）

```python
# stores/vector.py（伪代码）
model = SentenceTransformer(model_id, revision=model_rev, device="cpu")
model.eval()
vecs = model.encode(
    texts,
    batch_size=32,
    normalize_embeddings=True,  # ★ 必须：Cosine 与 L2 归一化配套
    convert_to_numpy=True,
    show_progress_bar=False,
)
```

- **`normalize_embeddings=True`**：Cosine 距离下向量必须单位化，否则同一文本在不同 batch 里分数会漂。
- **fp32**：不做 fp16/量化（P1 不做 ANN，性能不敏感；fp16 会引入数值不稳定）。
- **`device="cpu"`** 显式指定：避免机器有 GPU 时行为不一致（可复现优先）。
- **批量**：`batch_size=32`（内存与吞吐折中），可由配置 `vector.batch_size` 覆盖。

### 5.3 嵌入内容与查询侧前缀

| 对象 | 文本构造 | 前缀 |
|---|---|---|
| `papers`（P1） | `title + "\n\n" + (abstract or "")`；超 8192 token 截断 | 无（bge-m3） |
| `chunks`（P3） | `section + "\n" + chunk_text` | 无 |
| 查询 | 用户/系统查询原文 | 无（bge-m3）；切 bge-en 时由 `policy` 加固定前缀 |

- 空摘要论文**允许**入库（只用标题编码）。**payload 仍是 §2.6 的六字段，不新增 `has_abstract`**：
  "有无摘要"由 SQLite `papers.abstract IS NULL` 判断，不进向量 payload（避免两边口径漂移）。
  若 P3 确实需要按此过滤，需另提 payload 扩展 ADR。
- `text_sha` = sha256(规范化后的文本)（UTF-8、去首尾空白、`\r\n`→`\n`）：**归一化必须在哈希前完成**，
  否则同一文本两种换行会算两次嵌入。

---

## 6. D5/D6：缓存与确定性

### 6.1 缓存（`embeddings` 表，ADR-0005 §3.5）

```sql
-- 键：text_sha + model_id + model_rev；值：float32 小端 BLOB（已 L2 归一化）
INSERT INTO embeddings(text_sha, model_id, model_rev, dim, vec, created_at)
VALUES (?,?,?,?,?,?) ON CONFLICT DO NOTHING;
```

- **命中即跳过编码**：同文本跨 run、跨 topic 零成本（这正是 F8"缓存即复现性来源"的延伸）。
- **不同模型不混用**：`(model_id, model_rev)` 在键里 → 换模型不会读到旧向量。
- **体积**：1024×4 B = 4 KB/行；2 万篇 ≈ **80 MB**；换模型后旧行保留（可对照），按 `model_rev` 批量清理。
- 编码失败（OOM/异常）**不写缓存**，并抛 `E_VECTOR_ENCODE_FAILED`（附批大小与文本长度），由调用方降级为"不入向量"。

### 6.2 可复现性

| 措施 | 实现 |
|---|---|
| 模型版本固定 | `SentenceTransformer(..., revision=<model_rev>)`；`model_rev` 记入 `store_meta` 与 `embeddings` |
| 线程数固定 | `torch.set_num_threads(config.vector.num_threads)`（默认 8） |
| 确定性 | `model.eval()`、`torch.manual_seed(0)`、fp32、`device='cpu'` |
| 数值断言 | 同文本编码两次 → `cosine(v1,v2) ≥ 0.9999`（测试用例） |
| 顺序无关 | 打分与排序结果不依赖 batch 边界（测试：batch=1 与 batch=32 的 top-10 一致） |

---

## 7. D7：身份校验与启动自检

### 7.1 三重一致性（缺一即拒绝服务）

```python
dim_model = model.get_sentence_embedding_dimension()  # 1024
dim_meta = store_meta.dim  # 1024
dim_coll = qdrant.get_collection(active).config.params.vectors.size
assert dim_model == dim_meta == dim_coll == 1024
```

| 不一致 | 错误码 | 处置 |
|---|---|---|
| 模型维度 ≠ 1024 | `E_VECTOR_DIM_MISMATCH` | 拒绝启动写路径；提示改配置或换模型 |
| `store_meta.model_rev` ≠ 当前模型 | `E_VECTOR_MODEL_MISMATCH` | 要求走 §8 的重嵌入流程 |
| collection 缺失 / 为空但 `store_meta` 说已建 | `E_STORE_SCHEMA_MISMATCH` | `lit-agent stores rebuild --vector` |
| `active_collection` 指向不存在的 collection | `E_VECTOR_COLLECTION_MISSING` | 同上 |

### 7.2 collection 与 payload（对齐 §2.6，逐字）

```python
create_collection("papers_v1", vectors_config=VectorParams(size=1024, distance=Distance.COSINE))
# payload: {paper_id, title, year, source, topic_ids, published_at, discovered_at}
```

- `topic_ids`：P1 每次 run 只有一个 topic → 写 `[topic_id]`；P4 多归属时由重建脚本按图库 `BELONGS_TO` 重算。
- **payload 字段集不可自由扩张**：增字段要走 ADR（前端过滤与重建脚本都依赖它）。

### 7.3 测试替身（不下载 2.27 GB）

```python
class FakeEncoder:  # tests/fixtures/embedding.py
    dim = 1024

    def encode(self, texts, **kw):  # 确定性伪向量：字符哈希 → 单位向量
        ...
```

- **单测/集成测试一律注入 `FakeEncoder`**（`stores/vector.py` 通过构造参数接收 encoder，不在模块内 new）。
- 真实模型的验证放到 `tests/integration/test_embedding_real.py`，标记 `@pytest.mark.slow`（默认不跑）。

---

## 8. D8/D9：换模型流程与阈值重标定

### 8.1 重嵌入（禁止原地覆盖）

```
1) 预检：磁盘 ≥ 新旧 collection 之和；确认 model_rev 与目标一致
2) 建 papers_v2（size=1024）
3) 全量重嵌入：遍历 papers（title+abstract），命中 embeddings 缓存则复用；
   写 papers_v2（payload 与 v1 同构）
4) 对账：v2.points == papers 行数（有摘要口径：count(papers where abstract is not null) + 其余）
5) 抽样：随机 50 条查询，比较 v1/v2 top-10 重合度（记录，不设通过线）
6) 更新 store_meta.active_collection='papers_v2'、model_id、model_rev、dim
7) 观察 1 个 run；无异常 → 删 papers_v1
```

**回滚**：指针改回 `papers_v1` 即可（旧 collection 在删除前一直保留）。

### 8.2 阈值重标定（强制，Phase 2 的 `P2-GUARD-02`）

| 项 | Phase 0（词法口径） | 换 embedding 后 |
|---|---|---|
| Drift block / warn | 0.0777 / 0.0867（质心 0.0885 vs 0.0670） | **必须重算**：在同一批正/负样本上扫描阈值，按分布间隙定 block/warn（F9） |
| 判据 | TPR / FPR + 注入集 | 注入集 15/15 检出、0/3 误报（沿用 Phase 0 的验收口径） |
| 记录 | `RESULTS.md` §2.13 | `RESULTS-P1.md` / Phase 2 记录 **模型名+版本+阈值+样本量** |

> **门禁**：`store_meta.model_rev` 变化后，若 `results/calibration.json` 里没有对应 `model_rev` 的阈值记录，
> `drift` 守卫必须报 `E_GUARD_UNCALIBRATED` 并降级为 `warn-only`（不许用旧阈值直接 block）。

---

## 9. D10：明确不做（P1 范围）

1. ANN / HNSW / 量化（local 模式不支持，换形态需新 ADR）。
2. GPU 推理、多进程并行编码、fp16（可复现优先）。
3. sparse / colbert 混合检索（bge-m3 支持，但属 P3 检索升级）。
4. 云端 embedding、rerank 模型（如 bge-reranker）（P3 可选，另开 ADR）。
5. `chunks` collection 的实际写入（建表/建 collection 留位，P3 启用）。
6. 模型微调 / 领域适配训练。

---

## 10. 时间与成本预算

| 项 | 预估值 | 说明 |
|---|---|---|
| 模型下载 | 2.27 GB / 一次 | 视网速 5–20 min；可离线拷贝 |
| 5k 篇批嵌入（CPU, 8 线程, batch=32） | **约 20–40 min**（待实测） | 摘要 ~500 tokens；bge-m3 在 CPU 上约 4–8 篇/秒 |
| 2 万篇批嵌入 | **约 1.5–2.5 h**（待实测） | 可离线夜间跑；结果入 `embeddings` 表 |
| 增量（每周数百篇） | **秒级到分钟级** | 走缓存 + 只嵌新增 |
| 单次 top-10 查询 | 155 ms @5k、≈0.76 s @2 万 | Phase 0 实测（local 无 ANN） |
| 现金成本 | **$0** | 本地推理 |

> 上表"待实测"项在 Step 1.5 用 `lit-agent stores bench-embedding` 实测并写入 `RESULTS-P1.md`，
> 作为 §3.2 复评条件（p95/规模）的输入。

---

## 11. Impact

| 模块 | 影响 |
|---|---|
| `pyproject.toml` | 新增 `sentence-transformers`、`numpy`（本 ADR 授权） |
| `stores/vector.py` | 实现 `get_client()` 单例、`ensure_collection`、`Embedder`（注入式）、`encode→upsert`、`search`、身份校验 |
| `config.py` | 新增 `vector: {model_id, model_rev, dim:1024, batch_size, num_threads, hf_home, active_collection}` |
| `db/tables.py` | `embeddings`、`store_meta`（ADR-0005 已含） |
| `doctor.py` | 新增：模型存在性/维度/`store_meta` 一致性/离线可用性检查 |
| `graph/guards.py` | drift 阈值来源改为"标定记录"，未标定即 `warn-only`（P2） |
| `agents/reporter.py` | P1 仍用词法检索证据；P3 切向量后需重跑 grounding 基线 |
| `eval/metrics.py` | 新增 `embedding_cache_hit_rate`、`vector_points`、`embedding_cost_time` 指标 |
| `tests/` | `FakeEncoder` 注入；真实模型用例标 `slow` |

---

## 12. Migration

1. **无数据迁移**：Phase 1 新建库；Phase 0 的 `out/data/qdrant` 不迁移。
2. 若曾用"确定性占位向量"（旧 DG-1 的 C 方案）跑过：**删 `data/qdrant` 重建**，
   `store_meta` 三行按 D1 重写（`model_id='BAAI/bge-m3'`）。
3. 配置迁移：`config.example.yaml` 增加 `vector:` 段（`config.yaml` 需人工补，`doctor` 给出提示不静默补默认）。

---

## 13. Verification（验收命令与判据）

```powershell
uv run lit-agent doctor                       # 期望：vector 检查项 OK（模型存在 / dim=1024 / store_meta 一致）
uv run lit-agent stores rebuild --vector      # 期望：papers 点数 == 语料论文数（有摘要口径）
uv run pytest -q tests/unit -k "vector or embedding"          # 用 FakeEncoder，不下载模型
uv run pytest -q tests/integration -k "vector_store" -m "not slow"
uv run pytest -q tests/integration -k "embedding_real" -m "slow"   # 需已下载模型，手动触发
uv run lit-agent stores bench-embedding --limit 500           # 实测吞吐/内存，写 RESULTS-P1
```

| # | 判据 | 方法 |
|---|---|---|
| V1 | 维度契约 | `model.get_dimension() == store_meta.dim == collection.size == 1024`；故意改成 768 → `E_VECTOR_DIM_MISMATCH` |
| V2 | 向量归一化 | 任意编码结果 `‖v‖≈1`（±1e-5） |
| V3 | 确定性 | 同文本两次编码 `cosine ≥ 0.9999`；batch=1 与 batch=32 的 top-10 一致 |
| V4 | 缓存命中 | 二次编码同文本 → `embeddings` 行数不变，耗时 ≈0 |
| V5 | 模型切换守卫 | 改 `model_rev` 后启动 → `E_VECTOR_MODEL_MISMATCH`，提示走重嵌入 |
| V6 | 重建一致 | 删 `data/qdrant` → `stores rebuild --vector` → 点数一致 + 同 query top-10 集合一致 |
| V7 | payload 契约 | 写入后读回 payload，键集合 == §2.6 六字段 |
| V8 | 过滤生效 | `search(..., filter=year>=2024)` 返回子集且不越界 |
| V9 | 未标定守卫 | 删掉 `calibration.json` 对应条目 → drift 守卫 `E_GUARD_UNCALIBRATED` → 仅 warn（P2 用例） |
| V10 | 离线 | `HF_HUB_OFFLINE=1` 下用已缓存模型跑通一次编码 |

---

## 14. Risks & Open questions

| 风险 | 现状 | 缓解 |
|---|---|---|
| CPU 批嵌入慢（2 万篇 1.5–2.5 h） | 可接受（离线、一次性） | 增量靠缓存；如需更快 → ONNX runtime（V10 之后实测再定，需 ADR） |
| Windows 上 torch 安装体积/兼容 | 待 Step 1.5 实测 | 记录 `uv sync` 耗时与 wheel 版本；失败则退 bge-large-en-v1.5（更小） |
| `HF_HOME` 落在中文路径 | Kuzu 同样的坑（ADR-0003） | `doctor` 校验 ASCII；默认 `data/models/` |
| 换模型后阈值全偏 | 已知（F9） | §8.2 门禁：未标定只 warn |
| 中文摘要退化（若切 bge-en） | 已知 | 语料以英文为主；如占比 >5% → 保持 bge-m3 |
| `papers` payload 的 `topic_ids` 在多归属下失真 | P1 单 topic 无此问题 | P4 由 `BELONGS_TO` 重建，写进 rebuild 脚本 |

**待实测清单（Step 1.5 完成并写 `RESULTS-P1.md`）**：`uv sync` 时长与新增体积、模型下载时长、
5k/2 万篇批嵌入耗时与内存峰值、`data/qdrant` 磁盘占用、top-10 p95（5k/2 万）、`build` 与 `search` 的 CPU 占用。
