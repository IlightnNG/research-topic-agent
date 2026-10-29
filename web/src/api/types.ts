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
  claim_ids?: string[];
  claim_indexes?: number[];
  kind?: string;
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
  language?: string;
  generated_by?: string;
  fallback_count?: number;
  coverage?: number;
  word_count?: number;
  fallback_reason?: string | null;
}

export interface AuthorDetail {
  author_id: string;
  name: string;
  orcid: string | null;
  institution: string | null;
  works_count: number;
  papers: { paper_id: string; title: string; year: number | null; source: string }[];
  coauthors: { author_id: string; name: string; shared_papers: number }[];
}

export interface PaperDetail {
  paper_id: string;
  title: string;
  abstract: string;
  source: string;
  year: number | null;
  pdf_path: string | null;
  pdf_url: string | null;
  pdf_available: boolean;
  authors: { author_id: string; name: string }[];
  claims: { claim_id: string; text: string; snippet: string }[];
}

export interface RunDetail {
  id: string;
  topic_id: string;
  state: string;
  stage: string | null;
  period?: string | null;
  report_language?: string | null;
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
  reason_code?: string | null;
  ts: string;
}

export interface ChatSession {
  id: string;
  topic_id: string;
  created_at: string;
  last_message_at?: string | null;
  preview?: string | null;
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


export interface SourceSuggestion {
  venues: { name: string; source_id: string | null; confidence: number }[];
  queries: string[];
  from_year: number | null;
  source: string;
}

export interface SourcePreview {
  selector: Record<string, unknown>;
  since: string;
  sample_count: number;
  items: { paper_id: string; title: string; year: number | null; source: string }[];
}

export interface SourceConfig {
  source: "openalex";
  selector: {
    venue_ids: string[];
    queries: string[];
    from_year: number | null;
  };
}
