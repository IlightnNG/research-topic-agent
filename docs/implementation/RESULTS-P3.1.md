# RESULTS — Phase 3.1（修复与体验补齐）

> 口径：只记实测；数字由命令产出。
> 规范：`phase3.1-fixes-and-polish.md`（S1–S12 / H1–H12，已收尾）。

## 0. 一页摘要

| 指标 | 结果 |
|---|---|
| 阶段 | **Phase 3.1 完成** |
| 后端 | `pytest` **569 例**（exit 0） |
| 验证器 | `verify_phase3 13/13`、`verify_phase2_1 13/13`、`verify_phase2_2 8/8` |
| 前端 | `playwright` **16 passed**、`typecheck` ✓、`build` ✓ |
| 关键修复 | `.env` 加载、guard 误报、会话隔离/切换、UI 英文、Chat 语言镜像、report 英文 |

## 1. 交付

| 问题 | 修复 |
|---|---|
| `.env` 不生效 | `load_settings(dotenv_path=)`；真实 env > `.env` > YAML；支持 `API_KEY`/`API_KEY_ENV` 两种写法 |
| 模型不通用 | `.env` 支持 `NAME/BASE_URL/MODEL/API_KEY`；`.env.example` 给 DeepSeek/OpenAI/OpenRouter/Ollama 模板；health 暴露 `key_present` |
| guard 误报 `[3,3,0]` | 合并累计 counters 后再喂守卫；健康 run 不再 stagnation，空检索仍 repair/degrade |
| UI 中英混排 | UI/错误/状态全英文；语言切换入口移除（i18n 保留给设置页） |
| 会话不能切 | preview/last_message_at、点击切换、localStorage 恢复、请求竞态丢弃 |
| Chat 无证据 | 中英术语桥接；LLM rewrite（失败回落）；中文提问中文答、默认英文 |
| Report 中文 | 报告模板、claims 占位、refs 全部英文；默认英文 |

## 2. Chat LLM 实测（真实 `deepseek-flash`）

```text
最小调用：OK（req 6 / resp 1）
Chat rewrite：llm_used=true，citations=3，trace=[llm_rewrite, search_topic, loop]
```

## 3. 已知限制

| 限制 | 说明 | 去向 |
|---|---|---|
| Report 短 | 证据摘要（一 claim 一行），3–8 条、几百字符；非完整周报 | phase3.2 synthesis |
| 旧报告中文 | 历史数据不迁移 | 重新生成 |
| Chat 答案抽取式 | LLM 只改写 query，答案不自由生成 | 3.2 可选 |
| 语言切换 | 无 UI 入口 | 设置页 |
| e2e 关闭 LLM | `LIT_AGENT_PIPELINE__LLM=off`，省 token | 保持 |

## 4. 下一步（phase3.2）

1. Chat 流式/可恢复、引用抽屉、工具轨迹分组；
2. Report synthesis（引言/对比/缺口）+ 生成页语言选择；
3. 评测增强（RAGAS 风格 + 轨迹断言）。
