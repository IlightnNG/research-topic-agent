# Frontend Design

> Version: 1.0 (2026-11-01)
> Scope: Vue 3 report/chat frontend
> Status: F1–F6 implemented; real API integration done in Phase 4.1.7
> UI language: English only

---

## 1. Product Summary

The default page is a **Topics** page.

Each Topic opens either:

```text
Report
Chat
```

Report and Chat share the same top-level shell:

```text
fixed topic header
collapsible left list
main interaction area
collapsible right inspector
```

Report generation is organized by **Run**. Each Run owns its own compact tab
group. Chat is organized by **Conversation**.

The frontend is a thin Interface layer:

```text
Vue UI → HTTP/SSE API → Workflow/Kernel/Tools
```

It must not import domain services, run SQL, or build report content locally.

### Topic is a scope contract

A Topic is not just a label. It is the **scope boundary** passed into the
workflow:

```text
fixed direction: AI agents / FPGA / ...
optional description
optional keywords
optional exclusions
optional constraints
```

The agent must stay inside that direction and must not drift into unrelated
fields.

Before retrieval, the backend rewrites the raw Topic into a clear
`TopicBrief`:

```text
normalized title
scope statement
inclusion criteria
exclusion criteria
search queries
```

This is a language-level rewrite, not a translation and not a change of intent.
The original Topic is preserved for display; the normalized brief is what the
workflow uses.

The UI must show:

```text
original Topic name
normalized scope (header chip / popover)
topic normalization step in Trajectory
```

### Run controls

A running Run can be paused at a checkpoint boundary and resumed later:

```text
running → pausing → paused → running
```

Pause must not lose completed Nodes; Resume continues from the latest
checkpoint. Runs and Chat conversations can be deleted from their lists.

---

## 2. Non-Goals

```text
production design system
authentication / multi-tenant
rich report editor
mobile-first layout
complex graph visualization (inspector is a placeholder)
```

---

## 3. Routes

```text
/                                      Topics
/topics/:topicId/report?run=:runId     Report shell
/topics/:topicId/chat?conversation=:id Chat shell
```

Rules:

- `/` is always the Topics page.
- Report / Chat buttons on a Topic navigate to the corresponding route.
- Back returns to `/`.
- `run` query selects the active Run.
- `conversation` query selects the active Chat.
- Invalid IDs fall back to the nearest valid state with an inline error.

---

## 4. Layout

### 4.1 Topics Page

```text
┌──────────────────────────────────────────────────────────┐
│  Research Topics                         [+ New Topic]  │
├──────────────────────────────────────────────────────────┤
│  Topic card                                             │
│  Title                                                  │
│  Description                                            │
│  [Report]  [Chat]                                       │
├──────────────────────────────────────────────────────────┤
│  Topic card ...                                         │
└──────────────────────────────────────────────────────────┘
```

Requirements:

- Topic cards are the primary content.
- Each card has `Report` and `Chat` actions.
- `New Topic` opens a modal.
- Empty state: “No topics yet. Create your first topic.”
- Topic creation modal fields:
  - `Direction` required — short fixed scope, e.g. `AI agents`, `FPGA acceleration`
  - `Description` optional — what belongs in this topic
  - `Keywords` optional — comma-separated
  - `Exclusions` optional — comma-separated terms or subfields to avoid
  - `Constraints` optional — e.g. only recent papers, methods, venues
  - `Create` / `Cancel`
- The modal helper text:

```text
Direction is the hard scope boundary for this Topic. The agent may refine it
into a normalized research brief, but must not broaden it.
```

- After creation, navigate to `/topics/:id/report`.
- Topic cards show direction, short description, and `Report` / `Chat`.
- These fields are workflow inputs, not UI-only metadata:

```text
direction     → hard scope boundary / normalized goal
description   → scope context
keywords      → retrieval hints
exclusions    → negative constraints
constraints   → year, venue, method, fulltext requirements
focus_hint    → per-run narrowing; must stay inside direction
```

- The normalized brief is generated per Topic and reused by Runs unless a Run
  adds a focus hint.

### 4.2 Topic Shell

```text
┌──────────────────────────────────────────────────────────────┐
│ ← Back   Topic title / description      [Report] [Chat]     │ 56px fixed
├──────────────┬────────────────────────────────┬──────────────┤
│ Left list    │ Main                           │ Inspector    │
│ 248px        │ flexible                       │ 300px        │
│ collapsible  │                                │ collapsible  │
│              │                                │              │
│ Runs / Chats │ Report tabs or Chat            │ Placeholder  │
│ + New        │                                │              │
└──────────────┴────────────────────────────────┴──────────────┘
```

- Header is fixed at the top.
- Left list can collapse to a narrow icon rail.
- Inspector can collapse to a narrow rail.
- Main area scrolls independently.
- Layout is desktop-first; at narrower widths side panels auto-collapse.
- Same shell is used for Report and Chat.

### 4.3 Top Header

Left to right:

```text
Back
Topic title
Scope chip
Report / Chat segmented control
```

- `Scope chip` opens a popover with the normalized `TopicBrief`.
- `Topic description` may be shown as a second line when space allows.
- `Report` and `Chat` are mutually exclusive.
- Switching preserves the current Topic.
- Header must not scroll away.
- If a Run is active, the Scope chip shows that Run's normalized brief;
  otherwise it shows the Topic's latest brief or the raw direction.

---

## 5. Report Page

### 5.1 Left: Run List

```text
┌────────────────────┐
│ Runs         [+ New]│
├────────────────────┤
│ ● Run #12           │
│   2m ago · Running  │
│                    │
│ ✓ Run #11           │
│   1h ago · Complete │
└────────────────────┘
```

Items show:

```text
status icon
short run label
relative time
status text
overflow menu
```

- Clicking a Run selects it.
- Selected Run has a clear active state.
- `+ New` opens the New Run modal.
- Overflow menu: `Delete`.
- Delete opens a confirm modal:

```text
Delete this run?
This removes the run, its trace, report, and paper tabs.
```

- If the run is running, the confirm copy adds:

```text
The run will be stopped first.
```

- After deletion, select the next run; if none, show the empty state.
- Collapsed mode shows icons only, with tooltips.

### 5.2 New Run Modal

Opened from the Report run list.

Fields:

```text
Research focus (optional)
  textarea
  placeholder:
  "e.g. multi-agent evaluation, RAG citation quality, ..."

Report language
  select: English (default) / Chinese
```

Copy:

```text
New Report Run
Focus your run on a subfield, method, or constraint. Leave blank to use the
topic's normalized direction.

Report language
English
Chinese
```

Behavior:

- `focus_hint` is optional.
- If blank, send `focus_hint: null` (or omit it) and use the Topic direction.
- `language` defaults to `en`.
- Submit sends:

```json
{
  "focus_hint": "...",
  "language": "en"
}
```

- While submitting: disable buttons, show loading.
- On success: close modal, select the new Run, show Trajectory tab.
- On failure: keep modal open and show the error.

### 5.3 Main: Run Tabs

Each Run has its own tab group.

Tabs:

```text
Trajectory     fixed, never closable
Report         fixed, never closable, appears when report exists
Paper: ...     closable
```

Rules:

- Tabs are compact: 30px height, 12px font, max width 180px.
- Tab bar scrolls horizontally when overflowing.
- Only paper tabs show a close icon.
- `Trajectory` and `Report` never show close.
- Selecting another Run switches to that Run’s tab group.
- On Run selection:
  - if a report exists → activate `Report`
  - else → activate `Trajectory`
- When a report becomes ready while the user is watching Trajectory:
  - add the Report tab
  - do **not** steal focus
  - show a small “Report ready” indicator on the tab
- If a report tab is somehow active but the report is missing:
  - fall back to Trajectory
  - show an inline error

### 5.4 Trajectory Tab

UX rules:

- tool call and result share one card keyed by `call_id`;
- thinking summaries are collapsed by default;
- node failure reason is visible inline and in the run-failed block;
- `run.started` is at the top of the timeline.

Detailed record: [`TRAJECTORY-UX.md`](TRAJECTORY-UX.md).

Purpose:

```text
make the run auditable
show progress
show tool calls
show thinking summaries
show errors
pause / resume the run
```

#### Run controls

In the Trajectory toolbar:

```text
Running:  [Pause]
Pausing:  [Pausing…] disabled
Paused:   [Resume]
Finished: no control
Failed:   no control
```

Pause semantics:

```text
pause is requested at the next step boundary / checkpoint
the current tool call is allowed to finish
no new tool calls start
completed Nodes are kept
```

Paused banner:

```text
Run paused
Node: evidence.extract
Step: 3
Checkpoint saved
[Resume]
```

Resume:

```text
POST /api/v2/runs/{runId}/resume
→ run resumes from the latest checkpoint
→ SSE reconnects
→ Trajectory continues
```

The UI must never imply an immediate hard interrupt. Copy uses “Pause requested”
until the backend confirms `paused`.

Checkpoint display:

```text
last_checkpoint: node_id, step, created_at
```

#### Topic normalization

The first Node in a report run is normally:

```text
topic.normalize
```

The Trajectory shows it like any other Node:

```text
Node: topic.normalize
  Thinking summary
  Tool: topic.rewrite
  Result: normalized scope brief
```

The normalized brief is shown in the Scope chip and may be expanded.

Layout:

```text
┌──────────────────────────────────────────────┐
│ Node progress                                │
│ [source.collect][evidence.extract][report…]  │
│ 2 / 4 nodes · report.generate · Running      │
├──────────────────────────────────────────────┤
│ Node: source.collect                    Done │
│  Thinking summary                            │
│  Tool: source.search                         │
│    args preview                              │
│    result summary · 1.2s                     │
│                                              │
│ Node: evidence.extract                Running│
│  Thinking summary                            │
│  Tool: claims.extract                        │
│    ...                                       │
└──────────────────────────────────────────────┘
```

#### Node progress

- One segment per Node.
- Segment states:

```text
pending
running
verifying
committed
degraded
skipped
failed
paused
```

- Status colors are subtle, not neon.
- Header text:

```text
<committed> / <total> nodes · <current node> · <status>
```

- Progress bar is intentionally simple in v1.
- Later: per-tool progress, elapsed time, retries.

#### Timeline record

Events are grouped by Node and ordered by time.

Each Node section can contain:

```text
Node started
Thinking summary
Tool call
Tool result
Verification
Node committed / degraded / skipped / failed
```

Tool call card:

```text
Tool name
args preview (truncated)
status
duration
expandable raw result
```

Thinking summary:

```text
short italic paragraph
```

Do not show raw hidden chain-of-thought. The backend must provide a
**thinking summary** field; the UI renders that summary.

Errors:

```text
red inline row
error code
short message
expandable details
```

Auto-scroll:

- follow new events only while the user is at the bottom
- if the user scrolls up, show “Jump to latest”

Replay:

- On Run selection, fetch the full trace first.
- Then subscribe to SSE.
- Deduplicate by event ID.
- Reconnect with `Last-Event-ID`.
- The trace must remain complete after refresh.

### 5.5 Report Tab

Rendered only when a report exists.

Content:

```text
title
state / word count
sections
```

Sections are dynamic; never hardcode section kinds in the frontend.

Each section:

```text
section title
markdown body
```

Paper references:

- citations / paper links are clickable.
- clicking opens a new Paper tab for that Run.
- clicking does not navigate away from the Report tab.

### 5.6 Paper Tab

Closable.

Tab title:

```text
short paper title or “Paper P1”
```

Behavior:

- If PDF URL exists: show PDF viewer.
- If no PDF: show metadata / abstract.
- If PDF fails to load: fall back to metadata / abstract.
- Paper tab fetches:

```text
GET /api/v2/papers/{paperId}
```

Fields:

```text
title
authors
year
venue
abstract
pdf_url
source_url
```

Metadata view:

```text
Title
Authors · Year · Venue
Abstract
Open source
```

PDF viewer:

```text
page controls
zoom
fit width
open in new window
```

Close behavior:

```text
close paper tab
→ activate previous active tab
→ else Report
→ else Trajectory
```

### 5.7 Right Inspector

Collapsible.

Default: collapsed on Report page.

Expanded:

```text
Citations
  (empty state: “Citation graph will appear here.”)

Authors
  (empty state: “Author relationships will appear here.”)
```

- Placeholder in v1.
- Future: citations, author relations, paper metadata.
- Independent scroll.
- Do not block the main tab area.

---

## 6. Chat Page

Left:

```text
Conversations     [+ New]
```

Right:

```text
message list
composer
```

Top header is the same as Report.

Chat requirements:

```text
standard agent conversation
streaming assistant text
stop generation
markdown rendering
error state
auto-scroll only at bottom
```

Conversation delete:

```text
Conversation list item → overflow menu → Delete
→ confirm modal
→ DELETE /api/v2/conversations/{id}
→ if active, clear main area
→ select next conversation if any
```

No tabs on Chat.

---

## 7. Data Contracts

### Topic

```ts
interface Topic {
  id: string
  direction: string
  description?: string
  keywords?: string[]
  exclusions?: string[]
  constraints?: string[]
  created_at: string
}

interface TopicBrief {
  topic_id: string
  normalized_title: string
  scope_statement: string
  include_criteria: string[]
  exclude_criteria: string[]
  search_queries: string[]
  language: 'en' | 'zh'
  created_at: string
}
```

### Run

```ts
type RunState =
  | 'pending'
  | 'running'
  | 'pausing'
  | 'paused'
  | 'succeeded'
  | 'degraded'
  | 'failed'
  | 'aborted'

interface Checkpoint {
  node_id: string
  step: number
  created_at: string
}

interface Run {
  id: string
  topic_id: string
  state: RunState
  language: 'en' | 'zh'
  focus_hint?: string
  topic_brief?: TopicBrief
  last_checkpoint?: Checkpoint
  report_id?: string
  created_at: string
  started_at?: string
  finished_at?: string
}
```

### Trace

```ts
type NodeStatus =
  | 'pending'
  | 'running'
  | 'verifying'
  | 'committed'
  | 'degraded'
  | 'skipped'
  | 'failed'
  | 'paused'

interface NodeTrace {
  node_id: string
  title: string
  status: NodeStatus
  started_at?: string
  finished_at?: string
}

type TraceEvent =
  | { id: string; type: 'node.started'; node_id: string; ts: string }
  | { id: string; type: 'thinking.summary'; node_id: string; text: string; ts: string }
  | { id: string; type: 'tool.called'; node_id: string; call_id: string; tool: string; args_preview: string; ts: string }
  | { id: string; type: 'tool.result'; node_id: string; call_id: string; tool: string; ok: boolean; summary: string; duration_ms: number; ts: string }
  | { id: string; type: 'node.verifying'; node_id: string; ts: string }
  | { id: string; type: 'node.committed'; node_id: string; ts: string }
  | { id: string; type: 'node.degraded'; node_id: string; reason: string; ts: string }
  | { id: string; type: 'node.skipped'; node_id: string; ts: string }
  | { id: string; type: 'node.failed'; node_id: string; error: string; ts: string }
  | { id: string; type: 'topic.normalized'; node_id: string; brief: TopicBrief; ts: string }
  | { id: string; type: 'run.pausing'; ts: string }
  | { id: string; type: 'run.paused'; checkpoint?: Checkpoint; ts: string }
  | { id: string; type: 'run.resumed'; checkpoint?: Checkpoint; ts: string }
  | { id: string; type: 'run.finished'; state: RunState; ts: string }
```

### Tabs

```ts
type TabKind = 'trajectory' | 'report' | 'paper'

interface TabItem {
  id: string
  kind: TabKind
  title: string
  closable: boolean
  paperId?: string
}

interface RunTabState {
  tabs: TabItem[]
  activeTabId: string
}
```

---

## 8. API Surface

The frontend only calls Interface endpoints.

### Topics

```text
GET  /api/v2/topics
POST /api/v2/topics
GET  /api/v2/topics/{topicId}
GET  /api/v2/topics/{topicId}/brief
POST /api/v2/topics/{topicId}/normalize
DELETE /api/v2/topics/{topicId}
```

Create Topic body:

```json
{
  "direction": "AI agents",
  "description": "optional scope",
  "keywords": ["tool use", "planning"],
  "exclusions": ["robotics"],
  "constraints": ["2020+", "peer reviewed"]
}
```

### Runs

```text
GET  /api/v2/topics/{topicId}/runs
POST /api/v2/topics/{topicId}/runs
GET  /api/v2/runs/{runId}
GET  /api/v2/runs/{runId}/trace
GET  /api/v2/runs/{runId}/events     SSE
POST /api/v2/runs/{runId}/pause
POST /api/v2/runs/{runId}/resume
DELETE /api/v2/runs/{runId}
```

Create Run body:

```json
{
  "focus_hint": "optional subfield or constraint; null/omitted = Topic direction",
  "language": "en"
}
```

`language`:

```text
en = English (default)
zh = Chinese
```

It controls the generated report language, not UI language.

### Reports / Papers

```text
GET /api/v2/reports/{reportId}
GET /api/v2/papers/{paperId}
GET /api/v2/papers/{paperId}/pdf
```

### Chat

```text
GET    /api/v2/topics/{topicId}/conversations
POST   /api/v2/topics/{topicId}/conversations
GET    /api/v2/conversations/{conversationId}
POST   /api/v2/conversations/{conversationId}/messages
GET    /api/v2/conversations/{conversationId}/events   SSE
DELETE /api/v2/conversations/{conversationId}
```

---

## 9. Vue Architecture

```text
src/
  main.ts
  App.vue

  router/
    index.ts

  api/
    client.ts
    topics.ts
    runs.ts
    reports.ts
    papers.ts
    chat.ts
    events.ts

  stores/
    topics.ts
    runs.ts
    runTabs.ts
    trace.ts
    chat.ts
    layout.ts

  views/
    TopicsView.vue
    TopicLayout.vue
    ReportView.vue
    ChatView.vue

  components/
    ui/
      AppShell.vue
      TopBar.vue
      SegmentedControl.vue
      Sidebar.vue
      SidebarSection.vue
      List.vue
      ListItem.vue
      Button.vue
      IconButton.vue
      Modal.vue
      ConfirmDialog.vue
      OverflowMenu.vue
      Tabs.vue
      Tab.vue
      EmptyState.vue
      LoadingState.vue
      ErrorState.vue
      Badge.vue
      ProgressBar.vue

    report/
      RunList.vue
      NewRunModal.vue
      RunTabs.vue
      ScopePopover.vue
      NodeProgress.vue
      TrajectoryTimeline.vue
      ToolCallCard.vue
      ThinkingSummary.vue
      ReportViewer.vue
      PaperTab.vue
      PaperMetadata.vue
      PdfViewer.vue
      InspectorPanel.vue

    chat/
      ConversationList.vue
      ChatMessages.vue
      ChatComposer.vue

  styles/
    tokens.css
    base.css
```

Stack:

```text
Vue 3
TypeScript
Vite
Vue Router
Pinia
CSS variables
lucide-vue-next icons
marked + DOMPurify
pdfjs-dist
```

Do not add a heavy UI framework. The product needs a small, consistent set of
custom components.

---

## 10. Components

### Buttons

Variants:

```text
primary
secondary
ghost
danger
icon
```

Sizes:

```text
sm: 28px
md: 34px
```

### Lists

Used by Topics, Runs, Conversations.

```text
List
ListItem
  leading icon / status
  title
  subtitle
  trailing action
  active state
```

### Tabs

```ts
interface TabItem {
  id: string
  label: string
  closable?: boolean
  badge?: string
}
```

Props:

```ts
tabs: TabItem[]
activeId: string
compact?: boolean
```

Events:

```ts
select(id)
close(id)
```

Rules:

- compact tabs are 30px high.
- close is only shown for `closable`.
- horizontal scroll for overflow.
- active tab has a 2px bottom accent.

### NodeProgress

Props:

```ts
nodes: NodeTrace[]
currentNodeId?: string
```

Renders:

```text
segmented bar
node labels
status
x / y complete
```

### Modal

Used by:

```text
New Topic
New Run
```

Requirements:

```text
focus trap
Escape closes
click backdrop closes (unless submitting)
footer actions
max width 480px
```

### EmptyState

Used by:

```text
no topics
no runs
no conversations
no report yet
inspector placeholder
```

---

## 11. Visual System

### Direction

```text
academic
quiet
clean
low saturation
information first
```

No gradients, no glassmorphism, no decorative illustrations.

### Tokens

```css
:root {
  --bg: #f7f7f5;
  --surface: #ffffff;
  --surface-muted: #f2f2ef;
  --border: #e3e3de;
  --border-strong: #cfcfc8;

  --text: #1f2328;
  --text-muted: #6b7280;
  --text-faint: #9ca3af;

  --accent: #1f5f8b;
  --accent-soft: #e8f0f6;

  --success: #2f7d4f;
  --warning: #9a6b1f;
  --danger: #b33a3a;

  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;

  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 28px;

  --font-sans: Inter, ui-sans-serif, system-ui, sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, monospace;
}
```

### Typography

```text
page title       24px / 600
section title    18px / 600
body             14px / 1.55
small            12px / 1.45
mono/trace       12px / 1.5
```

### Layout dimensions

```text
top bar           56px
left sidebar      248px
left collapsed     48px
inspector         300px
inspector collapsed 44px
tab height         30px
content padding    24px
content max-width 920px
```

### Rules

```text
all spacing from tokens
all colors from tokens
no arbitrary one-off values unless layout-specific
component styles scoped
shared visual rules live in ui components
```

---

## 12. State Management

### Stores

```text
topicsStore
  list, loading, create()
  briefByTopic
  normalize(topicId)

runsStore
  runsByTopic
  selectedRunId
  runDetail
  fetchRuns()
  createRun(topicId, focusHint, language)
  selectRun()
  pause(runId)
  resume(runId)
  deleteRun(runId)

runTabsStore
  tabsByRun: Map<runId, RunTabState>
  ensureRunTabs(runId, reportExists)
  openPaper(runId, paper)
  closeTab(runId, tabId)
  activate(runId, tabId)

traceStore
  traceByRun
  lastEventIdByRun
  loadTrace()
  appendEvent()
  reconnect()

chatStore
  conversations
  activeConversation
  messages
  send()
  deleteConversation(id)
```

### Tab initialization

```text
selectRun(run):
  state = tabsByRun.get(run.id) ?? create
  ensure Trajectory
  if run.report_id:
      ensure Report
      active = Report
  else:
      active = Trajectory
```

### Persistence

```text
sidebar collapsed state   localStorage
inspector collapsed state localStorage
report language default   localStorage (last used)
active topic/run          route query
tabs                      in-memory; rebuild on refresh
paper tabs                not persisted
```

On refresh:

```text
reload topic/run
if report exists → Report active
else → Trajectory active
```

---

## 13. Event Handling

- Load full trace before opening SSE.
- Deduplicate events by ID.
- Keep `lastEventId`.
- Reconnect with `Last-Event-ID`.
- If SSE disconnects:

```text
show “Reconnecting…”
retry with backoff
fall back to polling run status
```

- On `run.finished`:
  - update run state
  - if succeeded and report exists, add Report tab
  - refresh report metadata
- On `node.failed`:
  - mark node failed
  - keep trace visible
  - show error row
- On `run.failed`:
  - stop reconnect timer
  - keep trace available
- On `run.pausing`:
  - set run state to `pausing`
  - disable Pause
  - keep trace visible
- On `run.paused`:
  - set run state to `paused`
  - show checkpoint banner
  - show Resume
- On `run.resumed`:
  - set run state to `running`
  - reconnect SSE if needed
  - continue trace
- On `run.deleted`:
  - remove run from list
  - clear tabs
  - select next run or empty state

---

## 14. Paper Interaction

Report citations must be mapped by the backend.

Recommended link format:

```html
<a data-paper-id="P1">[C1]</a>
```

Frontend:

```text
click
→ find or create Paper tab in current Run
→ activate it
→ fetch paper metadata
→ if pdf_url: load PDF
→ else: show metadata/abstract
```

Paper tab behavior:

```text
closable
not part of report content
does not change route
closing returns to previous tab
```

---

## 15. Error, Loading, Empty

Every async area needs:

```text
loading
empty
error
retry
```

Error component:

```text
short message
error code
Retry button
```

No silent failures.

---

## 16. Accessibility

```text
keyboard focus visible
modal focus trap
Escape closes modal
ARIA labels on icon buttons
tab list uses role=tablist
tab uses role=tab
aria-selected
color is not the only status indicator
```

---

## 17. Implementation Order

### Phase F1

```text
App shell
tokens
Topics page
Topic create modal
Report/Chat switch
```

### Phase F2

```text
Report shell
Run list
New Run modal (focus_hint + language)
Run selection
Tab store
Run delete
Topic brief display
```

### Phase F3

```text
Trajectory tab
Node progress
Trace API + SSE
Tool cards
Thinking summaries
Errors
Pause / resume + checkpoint banner
```

### Phase F4

```text
Report tab
Dynamic sections
Paper tabs
PDF viewer / metadata fallback
```

### Phase F5

```text
Chat page
Conversation list
Composer
Streaming
```

### Phase F6

```text
Inspector placeholder
responsive collapse
polish
accessibility
```

---

## 18. Acceptance Checklist

```text
[ ] default page is Topics
[ ] each Topic has Report and Chat
[ ] New Topic modal works
[ ] Topic has direction + optional description/keywords/exclusions/constraints
[ ] Topic brief is normalized by the backend
[ ] Topic brief is visible from the header
[ ] Report/Chat share the same header
[ ] left list collapses
[ ] inspector collapses
[ ] New Run modal has optional focus hint
[ ] blank focus hint falls back to Topic direction
[ ] New Run modal has language select, default English
[ ] each Run has its own tab group
[ ] tabs are compact
[ ] switching to a Run with a report shows Report
[ ] switching to a Run without a report shows Trajectory
[ ] Trajectory tab cannot be closed
[ ] Report tab cannot be closed
[ ] Paper tabs can be closed
[ ] node progress bar works
[ ] tool calls are recorded
[ ] thinking summaries are shown
[ ] full trace survives refresh
[ ] running Run has Pause
[ ] pausing/paused states are shown correctly
[ ] paused Run can Resume from checkpoint
[ ] checkpoint banner shows node/step
[ ] Run delete works with confirmation
[ ] Chat delete works with confirmation
[ ] report renders dynamic sections
[ ] paper reference opens a Paper tab
[ ] no PDF shows metadata/abstract
[ ] PDF failure falls back to metadata
[ ] all UI copy is English
[ ] common components are reused
[ ] theme and spacing are token-driven
```

---

## 19. Notes

The current implementation is an inline HTML page in the FastAPI app. This
document describes the **target Vue frontend**, not the current UI.

The Interface module owns this app. It calls only HTTP/SSE endpoints and never
imports Workflow, Kernel, Tools, or domain services.

Topic normalization is a backend concern. The frontend only displays the raw
Topic and the normalized `TopicBrief`; it must not rewrite or broaden scope
locally.

Pause/resume requires checkpoint support in the backend. The frontend must not
pretend a run is paused before the backend confirms it.


---

## 20. Implementation Status

F1–F6 are implemented in:

```text
web/
```

Run:

```powershell
cd web
npm install
npm run dev
```

Build:

```powershell
cd web
npm run build
```

Current behavior:

```text
Topics page + New Topic modal
Report / Chat switch
Report shell with collapsible Run list
New Report Run modal
  optional focus hint
  report language: English default, Chinese option
per-Run compact tabs
switch Run → Report if report exists, else Trajectory
Run delete with confirmation
Scope brief popover
```

Implemented in F3/F4:

```text
Node progress
Trace API client + SSE subscription
Tool calls
Thinking summaries
Trace errors
Pause / resume
Checkpoint banner
Dynamic report sections
Citation buttons
Paper tabs
Paper metadata / abstract fallback
PDF iframe viewer
```

Implemented in F5/F6:

```text
Chat conversation list
New conversation
Conversation delete
Message list
Streaming response
Stop generation
Chat composer
Inspector collapse
Citations tab
Authors placeholder
Citation click opens paper
```

Current integration:

```text
real API mode: VITE_USE_MOCK=false
topics / runs / trace / report / paper / chat endpoints available
mock mode remains the default for UI-only work
```

Mock mode:

```text
VITE_USE_MOCK=true
```

Seed data and localStorage adapter live in `web/src/api/mock.ts`.
