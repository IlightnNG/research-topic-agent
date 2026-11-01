# Lit Agent Web

Vue 3 frontend for the Lit Agent report/chat workspace.

Current scope: **F1–F6**.

```text
F1  Topics, Topic modal, Report/Chat switch
F2  Report shell, Run list, New Run modal, per-run tabs, Run delete
F3  Node progress, trace timeline, tool calls, thinking summaries, pause/resume
F4  Dynamic report, citation links, paper metadata/PDF tabs
F5  Chat conversations, streaming, stop, delete
F6  Inspector citations and authors placeholder
```

---

## Run

```powershell
cd web
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

Production build:

```powershell
npm run build
```

---

## Real API mode

F1–F6 can run against the real Python backend.

```text
web/.env.local

VITE_USE_MOCK=false
```

Start the backend from the repository root:

```powershell
$env:LIT_V2_DB='D:\lit-agent-store\temp\web.sqlite'
$env:LIT_V2_CORPUS='D:\lit-agent-store\p41-report-experiment'
uv run uvicorn lit_agent_v2.api.app:create_app --factory --port 8000
```

The Vite proxy sends `/api` to `http://127.0.0.1:8000`.

---

## Mock mode

For UI-only work:

```text
VITE_USE_MOCK=true
```

`src/api/mock.ts` stores Topics, Runs, Trace, Reports, Papers, and Chats in
`localStorage` so the UI can be reviewed without the backend.

---

## Routes

```text
/                                   Topics
/topics/:topicId/report?run=:runId  Report workspace
/topics/:topicId/chat               Chat workspace
```

---

## F1–F6 behavior

```text
default page is Topics
New Topic modal captures direction / description / keywords / exclusions / constraints
each Topic has Report and Chat
Report and Chat share the same header
header shows the normalized scope brief
left Run list collapses
New Run modal captures optional focus hint + report language
language defaults to English
each Run owns its own tab set
switch to a Run with report → Report tab active
switch to a Run without report → Trajectory tab active
Run delete uses confirmation
node progress and trace timeline
tool cards + thinking summaries
pause / resume + checkpoint banner
dynamic report sections
citation links open paper tabs
paper metadata / abstract fallback
chat conversation list, streaming, stop, delete
inspector citations / authors placeholder
```

Chat:

```text
conversation list + new + delete
message list + composer
streaming assistant text
stop generation
```

Real API mode supports topics, runs, trace, reports, papers, and basic chat.
Pause/resume is still boundary-based; real chat has no token streaming yet.

Trajectory and Report tabs are wired to the mock trace/report data. Pause/resume
uses mock checkpoints; the real backend must implement `/pause`, `/resume`,
`/trace`, and report/paper endpoints.

---

## Structure

```text
src/
  api/          HTTP client + mock adapter
  components/   ui / topics / layout / report
  router/       Vue Router
  stores/       Pinia: topics, runs, tabs, trace, reports, layout
  styles/       tokens + base
  types/        Topic / TopicBrief / Run / Tab contracts
  views/        Topics, Report, Chat
```

All UI copy is English.

Design docs: `docs/design/README.md`.

- `FRONTEND.md` — product/layout/component design
- `DEV-RUNBOOK.md` — startup and manual test
- `TRAJECTORY-UX.md` — trajectory rules

Startup and manual test guide: `docs/design/DEV-RUNBOOK.md`.
