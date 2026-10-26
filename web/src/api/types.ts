export interface Topic {
  id: string;
  name: string;
  description?: string;
  scope_statement?: string;
  status?: string;
}

export interface RunItem {
  id: string;
  period: string | null;
  state: string;
  stage: string | null;
  trigger?: string;
  focus_hint: string | null;
  error_code: string | null;
  started_at: string | null;
  finished_at: string | null;
  report_id: string | null;
  cost_usd: number;
}

export interface RunEvent {
  seq: number;
  ts: string;
  type: string;
  stage: string;
  agent?: string;
  severity?: string;
  payload: Record<string, unknown>;
}

export interface Claim {
  text: string;
  support: string;
  citations: Array<{ paper_id: string; snippet?: string }>;
}

export interface ReportSection {
  id: string;
  title: string;
  body: string;
  claim_ids: string[];
}

export interface Report {
  report_id: string;
  run_id: string;
  title: string;
  content_md: string;
  content_sha: string;
  degraded: boolean;
  n_claims: number;
  claims: Claim[];
  sections: ReportSection[];
}

export interface RunDetail {
  id: string;
  topic_id: string;
  state: string;
  stage: string | null;
  period?: string | null;
  focus_hint?: string | null;
  scope_sha?: string | null;
  error_code?: string | null;
  next_seq?: number;
}

export interface RunMetrics {
  run_id: string;
  source: "persisted" | "computed";
  claims_total?: number;
  cost_usd?: number;
  duration_by_stage?: Record<string, number>;
  duration_ms_total?: number;
  slowest_stage?: string | null;
  [key: string]: unknown;
}

export interface ChatCitation {
  paper_id: string;
  snippet: string;
}

export interface ChatTraceStep {
  tool: string;
  ok: boolean;
  hits?: number;
  steps?: number;
  stop?: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: ChatCitation[];
  trace: ChatTraceStep[];
  ts: string;
}

export interface ChatSession {
  id: string;
  topic_id: string;
  created_at: string;
}

export interface ChatState {
  topic_id: string;
  sessions: ChatSession[];
  session: ChatSession | null;
  messages: ChatMessage[];
}

export interface ChatPost {
  topic_id: string;
  session_id: string;
  message: ChatMessage;
  answered: boolean;
}
