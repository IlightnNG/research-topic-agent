import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import type { Report } from '@/types'

export const useReportsStore = defineStore('reports', () => {
  const reports = ref<Record<string, Report>>({})
  const loading = ref<Record<string, boolean>>({})
  const error = ref<Record<string, string>>({})

  async function load(runId: string, force = false): Promise<void> {
    if (reports.value[runId] && !force) return
    loading.value[runId] = true
    error.value[runId] = ''
    try {
      const report = await api.getReport(runId)
      if (report) reports.value[runId] = report
      else error.value[runId] = 'Report is not ready yet.'
    } catch (err) {
      error.value[runId] = err instanceof Error ? err.message : 'Could not load report.'
    } finally {
      loading.value[runId] = false
    }
  }

  return { reports, loading, error, load }
})
