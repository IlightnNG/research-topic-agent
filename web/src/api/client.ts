import type {
  ChatMessage,
  Conversation,
  CreateRunInput,
  CreateTopicInput,
  Paper,
  Report,
  Run,
  RunTrace,
  Topic,
  TopicBrief,
  TraceEvent,
} from '@/types'
import { mockApi } from './mock'

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { 'content-type': 'application/json' },
    ...init,
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    const error = payload?.error
    throw new Error(error?.message || error?.code || `Request failed: ${response.status}`)
  }
  return (await response.json()) as T
}

export const api = {
  listTopics(): Promise<Topic[]> {
    return USE_MOCK ? mockApi.listTopics() : request<Topic[]>('/api/v2/topics')
  },

  getTopic(id: string): Promise<Topic | undefined> {
    if (USE_MOCK) return mockApi.getTopic(id)
    return request<Topic>(`/api/v2/topics/${id}`).catch(() => undefined)
  },

  createTopic(input: CreateTopicInput): Promise<Topic> {
    if (USE_MOCK) return mockApi.createTopic(input)
    return request<Topic>('/api/v2/topics', {
      method: 'POST',
      body: JSON.stringify(input),
    })
  },

  getTopicBrief(topicId: string): Promise<TopicBrief | undefined> {
    if (USE_MOCK) return mockApi.getTopicBrief(topicId)
    return request<TopicBrief>(`/api/v2/topics/${topicId}/brief`).catch(() => undefined)
  },

  listRuns(topicId: string): Promise<Run[]> {
    if (USE_MOCK) return mockApi.listRuns(topicId)
    return request<Run[]>(`/api/v2/topics/${topicId}/runs`)
  },

  createRun(topicId: string, input: CreateRunInput): Promise<Run> {
    if (USE_MOCK) return mockApi.createRun(topicId, input)
    return request<Run>(`/api/v2/topics/${topicId}/runs`, {
      method: 'POST',
      body: JSON.stringify(input),
    })
  },

  pauseRun(runId: string): Promise<Run> {
    if (USE_MOCK) return mockApi.pauseRun(runId)
    return request<Run>(`/api/v2/runs/${runId}/pause`, { method: 'POST' })
  },

  resumeRun(runId: string): Promise<Run> {
    if (USE_MOCK) return mockApi.resumeRun(runId)
    return request<Run>(`/api/v2/runs/${runId}/resume`, { method: 'POST' })
  },

  retrySection(runId: string, sectionId: string): Promise<Run> {
    if (USE_MOCK) return mockApi.resumeRun(runId)
    return request<Run>(`/api/v2/runs/${runId}/sections/${sectionId}/retry`, {
      method: 'POST',
    })
  },

  deleteRun(runId: string): Promise<void> {
    if (USE_MOCK) return mockApi.deleteRun(runId)
    return request<void>(`/api/v2/runs/${runId}`, { method: 'DELETE' })
  },

  getTrace(runId: string): Promise<RunTrace> {
    if (USE_MOCK) return mockApi.getTrace(runId)
    return request<RunTrace>(`/api/v2/runs/${runId}/trace`)
  },

  async getReport(runId: string): Promise<Report | undefined> {
    if (USE_MOCK) return mockApi.getReport(runId)
    const link = await request<{ report_id: string }>(`/api/v2/runs/${runId}/report`)
    const payload = await request<{
      report: {
        report_id: string
        run_id: string
        title: string
        state: string
        word_count: number
        quality?: Report['quality']
      }
      sections: Report['sections']
    }>(`/api/v2/reports/${link.report_id}`)
    return {
      id: payload.report.report_id,
      run_id: payload.report.run_id,
      title: payload.report.title,
      state: payload.report.state,
      word_count: payload.report.word_count,
      sections: payload.sections,
      quality: payload.report.quality,
    }
  },

  getPaper(paperId: string): Promise<Paper | undefined> {
    if (USE_MOCK) return mockApi.getPaper(paperId)
    return request<Paper>(`/api/v2/papers/${paperId}`).catch(() => undefined)
  },

  listConversations(topicId: string): Promise<Conversation[]> {
    if (USE_MOCK) return mockApi.listConversations(topicId)
    return request<Conversation[]>(`/api/v2/topics/${topicId}/conversations`)
  },

  createConversation(topicId: string): Promise<Conversation> {
    if (USE_MOCK) return mockApi.createConversation(topicId)
    return request<Conversation>(`/api/v2/topics/${topicId}/conversations`, { method: 'POST' })
  },

  deleteConversation(conversationId: string): Promise<void> {
    if (USE_MOCK) return mockApi.deleteConversation(conversationId)
    return request<void>(`/api/v2/conversations/${conversationId}`, { method: 'DELETE' })
  },

  getMessages(conversationId: string): Promise<ChatMessage[]> {
    if (USE_MOCK) return mockApi.getMessages(conversationId)
    return request<ChatMessage[]>(`/api/v2/conversations/${conversationId}`)
  },

  sendMessage(
    conversationId: string,
    content: string,
    onChunk: (chunk: string) => void,
    signal?: AbortSignal,
  ): Promise<ChatMessage> {
    if (USE_MOCK) return mockApi.sendMessage(conversationId, content, onChunk, signal)
    return request<ChatMessage>(`/api/v2/conversations/${conversationId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content }),
      signal,
    })
  },

  subscribeRunEvents(runId: string, handler: (event: TraceEvent) => void): () => void {
    if (USE_MOCK) return () => undefined
    const source = new EventSource(`/api/v2/runs/${runId}/events`)
    const types: TraceEvent['type'][] = [
      'node.started',
      'thinking.summary',
      'tool.called',
      'tool.result',
      'node.verifying',
      'node.committed',
      'node.degraded',
      'node.skipped',
      'node.failed',
      'run.pausing',
      'run.paused',
      'run.resumed',
      'run.finished',
      'run.failed',
      'kernel.started',
      'kernel.step_started',
      'kernel.checkpoint',
      'kernel.tool_called',
      'kernel.tool_result',
      'kernel.model_retry',
      'kernel.repair',
      'kernel.context_compacted',
      'kernel.finished',
      'kernel.assistant_delta',
      'section.written',
      'section.failed',
    ]
    for (const type of types) {
      source.addEventListener(type, (raw) => {
        try {
          const outer = JSON.parse((raw as MessageEvent).data)
          const payload = outer.payload || {}
          handler({
            id: outer.seq ? `${runId}:${outer.seq}` : `${runId}-${Date.now()}`,
            type,
            node_id: outer.node_id,
            ts: outer.ts || new Date().toISOString(),
            ...payload,
          })
          if (type === 'run.failed' || type === 'run.finished') source.close()
        } catch {
          // Ignore malformed events; the next trace refresh will reconcile.
        }
      })
    }
    return () => source.close()
  },
}
