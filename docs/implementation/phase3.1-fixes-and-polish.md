# Phase 3.1 · 修复与体验补齐（详细施工方案）

> **版本**：**1.1.0**（2026-10-26，含“已落地/未验证/待做”快照）
> **类型**：修复型 —— 不改双层架构、不新增节点、不改事件契约
> **前置**：Phase 3 已收尾（`verify_phase3 13/13`、`pytest 551` 基线）
> **原则**：先修“不可用”，再修“不好用”；默认英文、中文可选；会话必须隔离；每一步可独立验收。
> **命名**：本文件取代口头“2.3 打磨”，后续统一 **phase3.1**。

---

## 0. 当前快照（重要）

> 本轮已经开始改代码，**不是纯计划**。下列状态以工作区为准。

| 项 | 状态 | 说明 |
|---|---|---|
| `.env` 加载 | ✅ 已改 | `load_settings(dotenv_path=)`；优先级：真实 env > `.env` > YAML > 默认 |
| `health.llm` | ✅ 已改 | 返回 `provider/model/base_url/key_present`（不含 key） |
| guard 误报 | ✅ 已改 | runner 合并 `state.counters` 与 `patch.counters` 后再喂守卫 |
| Chat 英文拒答 | ✅ 已改 | `no_evidence` / `unsupported`；migration `0005_chat_reason` 已应用 |
| 中文→英文检索桥接 | ✅ 已改 | `_BILINGUAL` 术语表（工具→tool 等） |
| 会话切换 | ✅ 已改 | `selectSession()` + 列表可点击；后端未知 session 返回 404 |
| 前端 i18n | ⚠️ 部分 | `web/src/i18n/index.ts`；Chat / 阶段标签 / 最慢阶段已接入；**其余组件仍有中文** |
| 默认英文 | ⚠️ 待验证 | default `en` 已实现；e2e 切换用例已写但**尚未跑通**（上一轮命令被中断） |
| Chat LLM 路径 | ❌ 未做 | 目前 Chat 仍是确定性检索，不调用 gateway |
| 全量回归 | ❌ 待跑 | 最新改动后尚未完整跑 `pytest` / `playwright` / `verify_phase3` |

**已知坑**：不要在同一条命令里“杀端口 + build + e2e”串跑，容易超时/被中断。拆成独立命令（见 §5.2）。

---

## 1. 目标与非目标

### 目标

1. **默认英文**：用户可见文本不再中英混排；可一键切中文并持久化。
2. **会话可用**：左侧会话可切换、历史隔离、刷新保持当前会话。
3. **配置可用**：`.env` 的 key 能被识别；任意 OpenAI 兼容模型可配置。
4. **诊断可信**：健康 run 不再出现 `E_GUARD_STAGNATION` 误报。
5. **Chat 有证据**：英文/常见中文问法都能命中；无命中给英文可操作提示。

### 非目标

- Chat token 流式/断线恢复、引用抽屉、工具轨迹分组 → **phase3.2**
- MCP、权限审批 UI、GoalRunner `resume` → **P4**
- 证据分级、RAGAS 评测 → **phase3.2**
- 不改 `NodeIO`、`GateResult`、`EventType`（ADR-0006/0007）

---

## 2. 问题、根因与修法

| ID | 现象 | 根因 | 修法 | 状态 |
|---|---|---|---|---|
| P1 | key 不生效、run 秒完成 | `.env` 从未被读取；`load_settings` 只读 `os.environ` | `_read_dotenv()` + 合并优先级；health 暴露 `key_present` | 已改 |
| P2 | `E_GUARD_STAGNATION [3,3,0]` | 守卫观测 `{**state, **patch}` 浅合并，report 的 `counters` 覆盖累计值 | 先合并 counters 再 `ctx.observation()` | 已改 |
| P3 | UI 英文、提示中文 | 前端硬编码中文；后端错误/拒答硬编码中文 | i18n 词条 + `reason_code`；后端 API 边界翻译（待做） | 部分 |
| P4 | 会话列表不能切、历史串 | 列表只展示；store 只加载 latest | `selectSession` + 按 session 查询 + 404 校验 | 已改 |
| P5 | 中文问题无命中 | 词面 hybrid、英文证据、Chat 无 LLM | 术语桥接（已做）；LLM rewrite/answer（待做） | 部分 |
| P6 | 模型名不可发现 | 默认 `deepseek-flash`，文档未写覆盖方式 | `.env`/env 变量 + health + 文档 | 已改 |

---

## 3. 模块设计

### M1 · 国际化（默认英文）

**契约**

- `Settings.ui.locale: Literal["en","zh"] = "en"`（新增，默认 en）。
- 前端 `web/src/i18n/index.ts`：`locale` ref（默认 en，localStorage 持久化）、`t(key)`、`setLocale()`。
- 后端 `src/lit_agent/i18n.py`：`t(key, locale="en")`；仅翻译 **API 返回给用户的 message**，不翻译事件/日志。
- 语言来源优先级：请求 `Accept-Language` > `ui.locale` > `en`。

**待做清单**

1. 后端：`api/routes/*.py` 里 `LitError(...)` 的用户消息改 key；`i18n` 提供 en/zh。
2. 前端：用 `rg` 找残留中文并替换：
   ```powershell
   rg -n "[\u4e00-\u9fff]" web/src --glob "!**/*.md"
   ```
   重点：`errors.ts`、`FailureCard.vue`、`ReportViewer.vue`、`RunWorkspace.vue`（暂停/注入/中止）、`TopicShell.vue`（aria）、`EmptyState.vue` 默认文案、`TopicsView.vue`、`GenerateReportDialog.vue`。
3. 语言切换按钮：已在 `TopicShell` 增加 `中文/EN`；确认在 Report/Chat 两页都可见。
4. 单测：`tests/i18n/test_catalog.py` 校验 en/zh key 集合一致、无空值。
5. e2e：默认英文 → 切中文 → 切回英文（已有用例，需跑通）。

**验收**：默认打开英文；切换后刷新保持；用户可见区域无裸中文；`rg` 只剩注释/文档。

---

### M2 · Chat 会话隔离与切换

**后端**

- `GET /api/topics/{id}/chat/sessions` 增加 `last_message_at`、`preview`（首条 user 消息前 40 字）。
- `GET /chat?session_id=` 校验 session 属于该 topic，否则 404（已做）。
- 消息查询严格 `WHERE session_id`（已做）。
- 可选：`DELETE /chat/sessions/{id}`（本阶段可不做）。

**前端**

- store：`session` 即当前会话；`selectSession(topicId, id)` 拉取该会话；`startNew()` 清空。
- 竞态：请求序号 `requestId`，旧响应丢弃；切换时 `loading` 防重复点击。
- UI：列表项可点击、当前高亮；空会话显示提示；新建后自动选中。
- 刷新：URL 可带 `?session=`（可选），或 localStorage 记住 `topicId→sessionId`。

**测试**

- 后端：A/B 两会话各 2 条消息，互不串（已有）；未知 session 404（已有）。
- e2e：新建会话（0 条）→ 点旧会话（>0 条）；再点新会话（0 条）。

---

### M3 · 配置与模型兼容

**契约**

```text
优先级：真实环境变量 > .env > config/config.yaml > 默认值
密钥：providers.cloud.api_key 只从 API_KEY_ENV 指向的变量读取
模型：LIT_AGENT_PROVIDERS__CLOUD__MODEL
网关：LIT_AGENT_PROVIDERS__CLOUD__BASE_URL
```

**待做**

1. `load_settings` 已有 `.env`；补 `tests/config/test_dotenv.py`（已有 2 例）。
2. `GET /api/health` 的 `llm` 字段（已做）；补 API 测试断言 `key_present` 与 `model`。
3. 文档：在 README/phase3.1 写 3 个示例（DeepSeek / OpenAI / 本地 Ollama）。
4. 安全：确认日志/事件/`config_version` 不含 key（`_config_hash` 已 sanitize）。

**验收**：`key_present=true`；改 `MODEL` 后 health 与 run 均生效；换 base_url 不报配置错。

---

### M4 · guard 误报修复

**根因**：`ctx.observation({**state, **patch}, name)` 让 `patch["counters"]` 覆盖累计值。

**已改**：runner 构造 `merged = {**state, **patch, "counters": {**state.counters, **patch.counters}}`。

**待做**

1. 回归测试：健康 3 篇 run 的 `guard_trigger` 不含 `E_GUARD_STAGNATION`（已加）。
2. 故障测试：`empty_retrieval` 仍能 repair/degrade（防止“修掉真问题”）。
3. 手工：生成一次周报，确认无“连续 2 步无新增”。

**验收**：健康 run 无该 guard；故障 run 仍按预期降级。

---

### M5 · Chat 证据命中与 LLM 路径

**现状**：`agents/chat.py` 走 `rewrite_query → search_topic → verify_claim`，全部确定性。

**待做**

1. **术语桥接**（已做）：`_BILINGUAL` 表，后续可外置为 `config/chat_synonyms.yaml`。
2. **LLM 路径**（P1）：
   - `answer(..., gateway=None)`；有 gateway 时：
     - 用 LLM 改写 query（失败回落规则）；
     - 用 LLM 生成答案，但**必须**输出 `citations`（结构化 JSON），无引用则拒答；
     - 记录 `llm_used` 到 trace。
   - API 用 `LLMGateway(settings)` 注入（key 缺失时为 None）。
3. 拒答：返回 `reason_code`（已做），前端按 `chat.no_evidence` 本地化。
4. 提示：无命中时 UI 显示“Try English keywords / add papers / check seed”。

**测试**

- 中文“工具使用”命中（已有）。
- 未知 query 英文拒答（已有）。
- 有 key 时 `llm_used=True`（用脚本化 gateway 单测，不真调网）。

---

## 4. 步骤（按顺序执行）

| 步 | 目标 | 主要文件 | 验收 | 预估 |
|---|---|---|---|---|
| **S1** | 跑通当前回归，确认基线 | — | `pytest` / `typecheck` / `build` 全绿 | 0.5 h |
| **S2** | M4 guard 回归 | `tests/observability/test_trajectory_replay.py` | 健康无 stagnation；空检索仍降级 | 0.5 h |
| **S3** | M3 配置/health | `config.py`、`health.py`、`tests/config` | `key_present=true`；model 覆盖 | 1 h |
| **S4** | M1 后端 i18n 边界 | `src/lit_agent/i18n.py`、`api/routes/*` | 错误响应 en/zh 正确 | 2 h |
| **S5** | M1 前端词条盘点 | `web/src/i18n/index.ts` + `rg` 清单 | en/zh key 集合一致 | 1 h |
| **S6** | M1 组件替换 | Chat/Report/Topics/失败卡/错误条 | 默认英文、无混排 | 1 d |
| **S7** | M1 e2e 与切换持久化 | `web/e2e/smoke.spec.ts` | 默认 en → zh → en | 2 h |
| **S8** | M2 会话元数据 | `db/repo/chat.py`、`api/routes/chat.py` | 列表带 preview/last_message_at | 2 h |
| **S9** | M2 切换/竞态/UI | `stores/chat.ts`、`TopicChatView.vue` | 切换不串、刷新保持 | 3 h |
| **S10** | M2 e2e | `smoke.spec.ts` | 新建→旧→新 三条断言 | 1 h |
| **S11** | M5 LLM Chat | `agents/chat.py`、`api/routes/chat.py` | 有 key 时 `llm_used`；无引用拒答 | 4 h |
| **S12** | 收尾与文档 | RESULTS、本文件 | H1–H12 全绿 | 2 h |

**依赖**：S1 必须先做；S8 依赖 S9；S11 依赖 S3（key 可用）。

---

## 5. 验收

### 5.1 H 判据

| # | 判据 | 命令/方式 |
|---|---|---|
| H1 | 默认 `en`，切 `zh` 后刷新保持 | e2e / 手工 |
| H2 | 用户可见文本无中英混排 | `rg "[\u4e00-\u9fff]" web/src` + 人工 |
| H3 | 后端错误/拒答支持 en/zh | `pytest tests/i18n` |
| H4 | 会话 A/B 历史不串 | `pytest tests/chat` |
| H5 | 左侧会话可切换且高亮 | e2e |
| H6 | 刷新后仍停留当前会话 | 手工/e2e |
| H7 | `.env` key 被识别 | `health.llm.key_present=true` |
| H8 | `MODEL`/`BASE_URL` 覆盖生效 | health + 单测 |
| H9 | 健康 run 无 `E_GUARD_STAGNATION` | 单测 + 手工 |
| H10 | 中/英 query 均能命中；未知 query 英文拒答 | 单测 + 手工 |
| H11 | 有 key 时 Chat `llm_used=true` | 单测（脚本化 gateway） |
| H12 | 回归：`pytest 基线+`、`verify_phase3 13/13`、e2e 14+ | 全量命令 |

### 5.2 命令（拆开跑，避免串行超时）

```powershell
. .\scripts\env.ps1

# 1) 后端
uv run pytest -q
uv run python scripts/verify_phase3.py --all

# 2) 前端
cd web
npm run typecheck
npm run build

# 3) e2e（先确保 8000/5173 没有残留旧进程；Playwright 会自启）
$env:PLAYWRIGHT_BROWSERS_PATH='D:\lit-agent-store\playwright'
npx playwright test e2e/smoke.spec.ts --reporter=line
```

> 上一轮“卡住”是因为把“杀端口 + build + e2e”放在同一条命令，且 e2e 自启服务超过等待窗口。拆开即可。

### 5.3 手工验收（10 分钟）

1. 启动后端/前端（两条终端）。
2. `/api/health` → `llm.key_present=true`、`model` 正确。
3. 生成周报 → 轨迹 10 阶段、无 stagnation、报告有 claims。
4. Chat 默认英文：问 `tool use` → 有引用；问中文 `工具使用` → 有引用；问 `zzz` → 英文拒答。
5. 点 `中文` → 拒答变中文；刷新仍中文；点 `EN` 恢复。
6. 新建对话 → 0 条；点旧会话 → 历史回来；再点新会话 → 仍 0 条。

---

## 6. 不变量与风险

**不变量**

- 不新增 `EventType`；payload 只增字段（ADR-0006）。
- 不改 `NodeIO` / `GateResult` / `ToolSpec` 必填字段（ADR-0007/0008）。
- `.env` 与日志中不得出现明文 key；`health` 只返回布尔。
- 会话查询必须带 `topic_id` 校验，禁止跨 topic 读取。

**风险与回滚**

| 风险 | 缓解 |
|---|---|
| i18n 改动面大，漏改 | 先 `rg` 盘点，再按组件替换；H2 卡口 |
| 会话切换竞态 | `requestId` 丢弃旧响应；e2e 覆盖 |
| guard 修复掩盖真停滞 | 保留 `empty_retrieval` 故障测试 |
| LLM Chat 成本/不确定 | 默认无 key 走确定性；有 key 才开；保留拒答 |
| 迁移 0005 回滚 | `alembic downgrade 0004_chat_trace` |

---

## 7. AI 实施建议（给后续执行者）

1. **每步先跑 H 判据再提交**；不要一次性改 5 个模块。
2. i18n **先后端后前端**：后端 key 稳定后，前端只映射。
3. 会话切换先写后端测试，再改 store，最后改 UI。
4. Chat LLM 必须**先写脚本化 gateway 测试**，再碰真实 key。
5. 任何“顺手重构”都拒绝：本阶段只修 P1–P6。

---

## 8. 与后续阶段关系

| 阶段 | 内容 |
|---|---|
| **phase3.2** | Chat 流式/可恢复、引用抽屉、工具轨迹分组、证据分级、RAGAS 风格评测 |
| **P4** | MCP、权限审批 UI、GoalRunner `resume`、子 agent |
| **论文** | 3.1 的修复不影响实验结论；3.2 的体验项才进 demo |

---

## 9. 变更记录

| 版本 | 日期 | 内容 |
|---|---|---|
| 1.1.0 | 2026-10-26 | 详细化：现状快照、M1–M5 设计、S1–S12、H1–H12、手工验收与风险 |
| 1.0.0 | 2026-10-26 | 首版修复清单 |
