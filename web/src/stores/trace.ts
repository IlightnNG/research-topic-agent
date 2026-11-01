import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import type { NodeStatus, RunTrace, TraceEvent } from '@/types'

export const useTraceStore = defineStore('trace', () => {
  const traces = ref<Record<string, RunTrace>>({})
  const loading = ref<Record<string, boolean>>({})
  const error = ref<Record<string, string>>({})

  async function load(runId: string): Promise<void> {
    loading.value[runId] = true
    error.value[runId] = ''
    try {
      traces.value[runId] = await api.getTrace(runId)
    } catch (err) {
      error.value[runId] = err instanceof Error ? err.message : 'Could not load trace.'
    } finally {
      loading.value[runId] = false
    }
  }

  function append(runId: string, event: TraceEvent): void {
    const trace = traces.value[runId]
    if (!trace || trace.events.some((item) => item.id === event.id)) return
    trace.events.push(event)
    if (!event.node_id) return
    const node = trace.nodes.find((item) => item.node_id === event.node_id)
    if (!node) return
    const status: Partial<Record<TraceEvent['type'], NodeStatus>> = {
      'node.started': 'running',
      'node.verifying': 'verifying',
      'node.committed': 'committed',
      'node.degraded': 'degraded',
      'node.skipped': 'skipped',
      'node.failed': 'failed',
    }
    const next = status[event.type]
    if (next) node.status = next
    if (event.type === 'run.paused') {
      for (const item of trace.nodes) if (item.status === 'running') item.status = 'paused'
    }
    if (event.type === 'run.resumed') {
      for (const item of trace.nodes) if (item.status === 'paused') item.status = 'running'
    }
  }

  return { traces, loading, error, load, append }
})
