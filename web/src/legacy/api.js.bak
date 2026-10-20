// 单一 API 客户端：所有路径与后端 §2.4 契约一一对应（错误统一抛 Error(code: message)）
const BASE = "";

async function request(path, options = {}) {
  const response = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const code = payload?.code || `HTTP_${response.status}`;
    const message = payload?.message || response.statusText;
    throw new Error(`${code}: ${message}`);
  }
  return payload;
}

export const api = {
  health: () => request("/api/health"),
  listTopics: () => request("/api/topics"),
  createTopic: (body) => request("/api/topics", { method: "POST", body: JSON.stringify(body) }),
  triggerRun: (topicId, body = {}) =>
    request(`/api/topics/${topicId}/run`, { method: "POST", body: JSON.stringify(body) }),
  getRun: (runId) => request(`/api/runs/${runId}`),
  listEvents: (runId, afterSeq = 0) =>
    request(`/api/runs/${runId}/events?after_seq=${afterSeq}&limit=500`),
  getRunReport: (runId) => request(`/api/runs/${runId}/report`),
  listTopicReports: (topicId) => request(`/api/topics/${topicId}/reports`),
  metrics: () => request("/api/metrics/summary"),
};

export function describeError(error) {
  return error instanceof Error ? error.message : String(error);
}
