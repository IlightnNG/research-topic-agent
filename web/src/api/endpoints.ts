import { request } from "./client";
import type { AuthorDetail, ChatPost, ChatState, PaperDetail, Report, RunDetail, RunEvent, RunItem, RunMetrics, Topic } from "./types";

export interface EventsPage {
  run_id: string;
  after_seq: number;
  items: RunEvent[];
  count: number;
}

export const api = {
  health: () => request<{ ok: boolean; sqlite: { schema_version: string; tables: number } }>("/api/health"),

  listTopics: () => request<Topic[]>("/api/topics"),
  getTopic: (topicId: string) => request<Topic & { sources?: Record<string, unknown> }>(`/api/topics/${topicId}`),
  createTopic: (body: Record<string, unknown>) =>
    request<{ id: string }>("/api/topics", { method: "POST", body: JSON.stringify(body) }),
  patchTopic: (topicId: string, body: Record<string, unknown>) =>
    request<Topic>(`/api/topics/${topicId}`, { method: "PATCH", body: JSON.stringify(body) }),
  topicCounts: (topicId: string) =>
    request<{ runs: number; reports: number }>(`/api/topics/${topicId}/counts`),

  listRuns: (topicId: string, limit = 30, offset = 0) =>
    request<{ items: RunItem[]; count: number }>(
      `/api/topics/${topicId}/runs?limit=${limit}&offset=${offset}`,
    ),
  triggerRun: (topicId: string, body: { run_id?: string; focus_hint?: string | null; wait?: boolean; report_language?: "en" | "zh" }) =>
    request<{ run_id: string; state?: string }>(`/api/topics/${topicId}/run`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getRun: (runId: string) => request<RunDetail>(`/api/runs/${runId}`),
  listEvents: (runId: string, afterSeq = 0) =>
    request<EventsPage>(`/api/runs/${runId}/events?after_seq=${afterSeq}&limit=500`),
  getReport: (runId: string) => request<Report>(`/api/runs/${runId}/report`),
  getPaper: (paperId: string) => request<PaperDetail>(`/api/papers/${paperId}`),
  getAuthor: (authorId: string) => request<AuthorDetail>(`/api/authors/${authorId}`),
  paperPdfUrl: (paperId: string) => `/api/papers/${paperId}/pdf`,
  getRunMetrics: (runId: string) => request<RunMetrics>(`/api/runs/${runId}/metrics`),
  createChatSession: (topicId: string) =>
    request<{ topic_id: string; session_id: string }>(`/api/topics/${topicId}/chat/sessions`, {
      method: "POST",
    }),
  getChat: (topicId: string, sessionId?: string) =>
    request<ChatState>(
      `/api/topics/${topicId}/chat${sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ""}`,
    ),
  postChat: (topicId: string, body: { message: string; session_id?: string }, signal?: AbortSignal) =>
    request<ChatPost>(`/api/topics/${topicId}/chat`, {
      method: "POST",
      body: JSON.stringify(body),
      signal,
    }),
  abortRun: (runId: string) =>
    request<{ run_id: string }>(`/api/runs/${runId}/abort`, { method: "POST" }),
  pauseRun: (runId: string) =>
    request<{ run_id: string; state: string }>(`/api/runs/${runId}/pause`, { method: "POST" }),
  resumeRun: (runId: string) =>
    request<{ run_id: string; state: string }>(`/api/runs/${runId}/resume`, { method: "POST" }),
  injectRun: (runId: string, prompt: string) =>
    request<{ run_id: string; pending: number }>(`/api/runs/${runId}/inject`, {
      method: "POST",
      body: JSON.stringify({ prompt }),
    }),
  metrics: () =>
    request<{ runs: number; events: number; reports: number; papers: number; llm_cost_usd: number }>(
      "/api/metrics/summary",
    ),
};

export type { AuthorDetail, PaperDetail, Report, RunDetail, RunEvent, RunItem, Topic };
