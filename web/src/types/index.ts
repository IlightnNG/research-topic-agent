export type ReportLanguage = 'en' | 'zh'

export type RunState =
  | 'pending'
  | 'running'
  | 'pausing'
  | 'paused'
  | 'succeeded'
  | 'degraded'
  | 'failed'
  | 'aborted'

export interface Topic {
  id: string
  direction: string
  description?: string
  keywords?: string[]
  exclusions?: string[]
  constraints?: string[]
  created_at: string
}

export interface TopicBrief {
  topic_id: string
  normalized_title: string
  scope_statement: string
  include_criteria: string[]
  exclude_criteria: string[]
  search_queries: string[]
  language: ReportLanguage
  created_at: string
}

export interface Run {
  id: string
  topic_id: string
  state: RunState
  language: ReportLanguage
  focus_hint?: string
  report_id?: string
  last_checkpoint?: Checkpoint
  created_at: string
  started_at?: string
  finished_at?: string
}

export interface CreateTopicInput {
  direction: string
  description?: string
  keywords?: string[]
  exclusions?: string[]
  constraints?: string[]
}

export interface CreateRunInput {
  focus_hint?: string | null
  language: ReportLanguage
  source_mode?: 'local' | 'online' | 'auto'
  limit?: number
}

export type TabKind = 'trajectory' | 'report' | 'paper'

export interface TabItem {
  id: string
  kind: TabKind
  title: string
  closable: boolean
  paperId?: string
}

export interface RunTabState {
  tabs: TabItem[]
  activeTabId: string
}


export type NodeStatus =
  | 'pending'
  | 'running'
  | 'verifying'
  | 'committed'
  | 'degraded'
  | 'skipped'
  | 'failed'
  | 'paused'

export interface NodeTrace {
  node_id: string
  title: string
  status: NodeStatus
  started_at?: string
  finished_at?: string
  error?: string
}

export interface Checkpoint {
  node_id: string
  step: number
  created_at: string
}

export type TraceEventType =
  | 'node.started'
  | 'thinking.summary'
  | 'tool.called'
  | 'tool.result'
  | 'node.verifying'
  | 'node.committed'
  | 'node.degraded'
  | 'node.skipped'
  | 'node.failed'
  | 'run.started'
  | 'run.pausing'
  | 'run.paused'
  | 'run.resumed'
  | 'run.finished'
  | 'run.failed'
  | 'context.compacted'
  | 'section.written'
  | 'section.failed'
  | 'kernel.started'
  | 'kernel.step_started'
  | 'kernel.checkpoint'
  | 'kernel.tool_called'
  | 'kernel.tool_result'
  | 'kernel.model_retry'
  | 'kernel.repair'
  | 'kernel.context_compacted'
  | 'kernel.finished'
  | 'kernel.assistant_delta'

export interface TraceEvent {
  id: string
  type: TraceEventType
  node_id?: string
  ts: string
  text?: string
  tool?: string
  call_id?: string
  args_preview?: string
  ok?: boolean
  summary?: string
  duration_ms?: number
  before?: number
  after?: number
  error?: string
  reason?: string
  reasons?: string[]
  state?: RunState
  checkpoint?: Checkpoint
  task?: string
  step?: number
  section_id?: string
  written?: number
  remaining?: number
  total?: number
}

export interface RunTrace {
  run_id: string
  nodes: NodeTrace[]
  events: TraceEvent[]
  checkpoint?: Checkpoint
  task?: string
  step?: number
  section_id?: string
  written?: number
  remaining?: number
  total?: number
}

export interface PaperLink {
  token: string
  paper_id: string
  label: string
}

export interface ReportSection {
  section_id: string
  kind: string
  title: string
  body: string
  paper_links?: PaperLink[]
}

export interface ReportQuality {
  accepted: boolean
  problems: string[]
  metrics?: {
    papers?: number
    fulltext?: number
    claims?: number
    sections?: number
    word_count?: number
    citation_coverage?: number
    empty_sections?: number
    uncovered_claims?: number
    duplicate_sentences?: number
  }
  audit?: {
    accepted: boolean
    status: string
    scores?: Record<string, number>
    problems?: string[]
  }
}

export interface Report {
  id: string
  run_id: string
  title: string
  state: string
  word_count: number
  sections: ReportSection[]
  quality?: ReportQuality
}

export interface Paper {
  id: string
  title: string
  authors: string[]
  year?: number
  venue?: string
  abstract: string
  pdf_url?: string
  source_url?: string
}


export interface Conversation {
  id: string
  topic_id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
}

export type ChatMessageState = 'done' | 'streaming' | 'stopped' | 'error'

export interface ChatMessage {
  id: string
  conversation_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
  state: ChatMessageState
}
