import { request } from "./client";
import type { Report, RunDetail, RunEvent, RunItem, Topic } from "./types";

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
  triggerRun: (topicId: string, body: { run_id?: string; focus_hint?: string | null; wait?: boolean }) =>
    request<{ run_id: string; state?: string }>(`/api/topics/${topicId}/run`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getRun: (runId: string) => request<RunDetail>(`/api/runs/${runId}`),
  listEvents: (runId: string, afterSeq = 0) =>
    request<EventsPage>(`/api/runs/${runId}/events?after_seq=${afterSeq}&limit=500`),
  getReport: (runId: string) => request<Report>(`/api/runs/${runId}/report`),
  abortRun: (runId: string) =>
    request<{ run_id: string }>(`/api/runs/${runId}/abort`, { method: "POST" }),
  metrics: () =>
    request<{ runs: number; events: number; reports: number; papers: number; llm_cost_usd: number }>(
      "/api/metrics/summary",
    ),
};

export type { Report, RunDetail, RunEvent, RunItem, Topic };
