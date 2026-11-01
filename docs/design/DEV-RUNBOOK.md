# Local Dev Runbook

> 用途：本地启动前后端，手动验证 Topics → Run → Trajectory → Report → Paper / Chat
> 平台：Windows + PowerShell
> 状态：已按本文命令联调通过

---

## Quick Start

### Terminal 1 — backend

```powershell
cd E:\大学\NUS\EE5003\agent
. .\scripts\env.ps1
$env:LIT_V2_DB='D:\lit-agent-store\temp\web-dev.sqlite'
$env:LIT_V2_CORPUS='D:\lit-agent-store\p41-report-experiment'
uv run uvicorn lit_agent_v2.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

### Terminal 2 — frontend

```powershell
cd E:\大学\NUS\EE5003\agent\web
$env:VITE_USE_MOCK='false'
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173/`.

---

## Quick Start · 100-paper full chain

Standalone (no backend):

```powershell
cd E:\大学\NUS\EE5003\agent
. .\scripts\env.ps1
uv run python scripts\demo100.py
```

Output:

```text
D:\lit-agent-store\v2-demo\
  source.json
  evidence.json
  report.json
  report.md
  final.json
```

API / UI mode:

```powershell
$env:LIT_V2_DB='D:\lit-agent-store\temp\demo100-api.sqlite'
$env:LIT_V2_CORPUS='D:\lit-agent-store\v2-eval\gold\corpora\agents'
$env:LIT_V2_DEMO_CHAIN='full'
$env:LIT_V2_DEMO_OUT='D:\lit-agent-store\v2-demo-api'

uv run uvicorn lit_agent_v2.api.app:create_app `
  --factory --host 127.0.0.1 --port 8000
```

Then create a Run normally. The trace has four Nodes:

```text
source.collect
  → evidence.extract
  → report.generate
  → finalize
```

Full-chain result: [`RESULTS-P4.1.8.md`](../implementation/RESULTS-P4.1.8.md).

---

## 1. 前置条件

### Python 后端

```powershell
cd E:\大学\NUS\EE5003\agent
. .\scripts\env.ps1
```

依赖已由 `uv` 管理。

根目录 `.env` 需要配置 LLM：

```text
LIT_AGENT_PROVIDERS__CLOUD__API_KEY=...
LIT_AGENT_PROVIDERS__CLOUD__BASE_URL=https://api.deepseek.com
LIT_AGENT_PROVIDERS__CLOUD__MODEL=deepseek-flash
```

如果 `.env` 不存在，复制：

```powershell
Copy-Item .env.example .env
```

然后填入 API key。

### 前端

```powershell
node --version
npm --version
```

需要 Node.js 18+。

首次运行：

```powershell
cd E:\大学\NUS\EE5003\agent\web
npm install
```

### 演示语料

当前联调使用：

```text
D:\lit-agent-store\p41-report-experiment
```

至少需要：

```text
papers.jsonl
```

每一行是一篇论文：

```json
{"paper_id":"P1","title":"...","abstract":"..."}
```

如果目录不存在，先创建 3 篇左右论文，避免报告为空。

---

## 2. 启动后端

打开 **Terminal 1**：

```powershell
cd E:\大学\NUS\EE5003\agent
. .\scripts\env.ps1

$env:LIT_V2_DB='D:\lit-agent-store\temp\web-dev.sqlite'
$env:LIT_V2_CORPUS='D:\lit-agent-store\p41-report-experiment'

uv run uvicorn lit_agent_v2.api.app:create_app `
  --factory `
  --host 127.0.0.1 `
  --port 8000
```

预期：

```text
Uvicorn running on http://127.0.0.1:8000
```

### 后端健康检查

另开 PowerShell：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v2/health
Invoke-RestMethod http://127.0.0.1:8000/api/v2/topics
```

Topics 应该返回 3 个种子方向：

```text
AI agents
FPGA acceleration
Scientific RAG
```

如果这里失败，先不要启动前端。

---

## 3. 启动前端（真实 API 模式）

打开 **Terminal 2**：

```powershell
cd E:\大学\NUS\EE5003\agent\web
$env:VITE_USE_MOCK='false'
npm run dev -- --host 127.0.0.1
```

预期：

```text
VITE ready
Local: http://127.0.0.1:5173/
```

打开：

```text
http://127.0.0.1:5173/
```

Vite 会把 `/api` 代理到：

```text
http://127.0.0.1:8000
```

### 使用 `.env.local` 代替环境变量

也可以在 `web/.env.local` 写：

```text
VITE_USE_MOCK=false
```

然后直接：

```powershell
cd web
npm run dev
```

注意：

```text
VITE_USE_MOCK=true  → 本地 mock
VITE_USE_MOCK=false → 真实后端
```

默认未设置时为 mock。

---

## 4. 手动测试流程

### 4.1 Topics

打开 `/`。

检查：

```text
[ ] 默认页是 Topics
[ ] 显示 3 个 Topic
[ ] 每个 Topic 有 Report / Chat
[ ] New Topic 弹窗可以创建
[ ] 创建后进入 Report 页面
```

### 4.2 创建 Run

进入：

```text
AI agents → Report
```

点击左侧 `+`（New run）。

弹窗：

```text
Research focus: 可填，也可留空
Report language: English / Chinese
```

建议第一次：

```text
Research focus: multi-agent evaluation
Language: English
```

检查：

```text
[ ] 创建后 URL 带 ?run=...
[ ] 左侧 Run 列表出现新 Run
[ ] Trajectory tab 自动激活
[ ] Node progress 显示 report.generate
```

### 4.3 Trajectory

等待 Run 完成。

检查：

```text
[ ] Node progress 从 running → committed
[ ] 出现 tool.called / tool.result
[ ] 有 thinking summary（真实 LLM 有 reasoning 时）
[ ] Run 状态变为 succeeded
[ ] 完成后多出 Report tab
```

如果 Run 很快结束，Pause 按钮可能来不及点，这是正常的。

### 4.4 Report

点击 Report tab。

检查：

```text
[ ] 报告标题
[ ] state / word count
[ ] 动态 section
[ ] [C1] 等 citation 是可点击按钮
```

点击一个 citation：

```text
[ ] 新增 Paper tab
[ ] Paper tab 可关闭
[ ] 关闭后回到 Report
```

注意：

```text
当前 PDF 使用 iframe
没有 PDF 时显示 metadata / abstract
```

### 4.5 Inspector

点击右侧 `>` 展开。

检查：

```text
[ ] Citations tab
[ ] 点击 citation 打开 Paper tab
[ ] Authors 是 placeholder
```

### 4.6 Chat

点击顶部 Chat。

检查：

```text
[ ] 左侧 Conversation 列表
[ ] + New conversation
[ ] 发送消息
[ ] 收到 assistant 回复
[ ] 删除 Conversation 有确认
```

真实后端目前不是 token streaming；mock 模式有流式效果。

### 4.7 删除 Run

左侧 Run 列表点 `⋯` → Delete run。

检查：

```text
[ ] 有确认弹窗
[ ] 删除后选择下一个 Run
[ ] 没有 Run 时显示空状态
```

---

## 5. API 手工冒烟

### 创建 Run

```powershell
$body = @{
  focus_hint = 'multi-agent evaluation'
  language = 'en'
} | ConvertTo-Json

$run = Invoke-RestMethod `
  -Method Post `
  -ContentType 'application/json' `
  -Body $body `
  http://127.0.0.1:8000/api/v2/topics/topic-ai-agents/runs

$run
```

### 轮询状态

```powershell
do {
  $state = (Invoke-RestMethod "http://127.0.0.1:8000/api/v2/runs/$($run.id)").state
  Write-Host $state
  Start-Sleep -Seconds 2
} while ($state -eq 'running')
```

### 查看 Trace

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/v2/runs/$($run.id)/trace" |
  ConvertTo-Json -Depth 8
```

### 查看 Report

```powershell
$link = Invoke-RestMethod "http://127.0.0.1:8000/api/v2/runs/$($run.id)/report"
$report = Invoke-RestMethod "http://127.0.0.1:8000/api/v2/reports/$($link.report_id)"
$report.report.title
$report.sections
```

### 删除 Run

```powershell
Invoke-RestMethod -Method Delete "http://127.0.0.1:8000/api/v2/runs/$($run.id)"
```

---

## 6. 构建检查

前端：

```powershell
cd E:\大学\NUS\EE5003\agent\web
npm run build
```

预期：

```text
vue-tsc --noEmit  pass
vite build        pass
```

后端：

```powershell
cd E:\大学\NUS\EE5003\agent
. .\scripts\env.ps1
uv run pytest -q tests/v2
uv run ruff check .
```

当前预期：

```text
135 passed
ruff clean
```

---

## 7. 常见问题

### 前端仍然显示 mock 数据

检查：

```powershell
echo $env:VITE_USE_MOCK
```

应为：

```text
false
```

或者在 `web/.env.local` 设置：

```text
VITE_USE_MOCK=false
```

重启 Vite。

### 创建 Run 失败：E_CORPUS_NOT_FOUND

检查：

```powershell
Test-Path $env:LIT_V2_CORPUS
Test-Path "$env:LIT_V2_CORPUS\papers.jsonl"
```

`LIT_V2_CORPUS` 必须是目录，不是文件。

### 创建 Run 后 failed

查看后端终端 traceback 和：

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/v2/runs/<run-id>/trace" |
  ConvertTo-Json -Depth 8
```

常见原因：

```text
LLM API key 缺失
LLM 输出 JSON 失败
报告 node 没有产出 content_md
```

### Report 一直 not ready

报告只在 Run succeeded 后存在。

检查：

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/v2/runs/<run-id>"
```

`report_id` 非空才说明报告已落库。

### Port 8000 被占用

```powershell
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
```

换端口后同步修改 `web/vite.config.ts` 的 proxy target。

### Port 5173 被占用

Vite 会自动换端口，以终端显示为准。

### 旧 SQLite schema / 数据混乱

换一个新的 DB 文件即可：

```powershell
$env:LIT_V2_DB='D:\lit-agent-store\temp\web-dev-2.sqlite'
```

不要随意删除已有数据库，除非确认不需要历史 Run。

---

## 8. 停止

两个终端分别：

```text
Ctrl + C
```

---

## 9. 当前实现边界

```text
Pause/Resume 在 step boundary 生效
单 Node 的 demo run 可能来不及暂停
真实 chat 无 token streaming；mock 模式有
PDF 使用 iframe + metadata fallback
主题 normalization 目前是确定性 brief
```
