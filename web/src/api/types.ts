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
