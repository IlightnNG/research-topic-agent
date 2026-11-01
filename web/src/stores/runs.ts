import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import type { CreateRunInput, Run } from '@/types'

export const useRunsStore = defineStore('runs', () => {
  const runs = ref<Run[]>([])
  const selectedRunId = ref('')
  const loading = ref(false)
  const error = ref('')

  const selectedRun = computed(() => runs.value.find((run) => run.id === selectedRunId.value))
  const runningRun = computed(() => runs.value.find((run) => run.state === 'running'))

  async function load(topicId: string): Promise<void> {
    loading.value = true
    error.value = ''
    try {
      runs.value = await api.listRuns(topicId)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Could not load runs.'
    } finally {
      loading.value = false
    }
  }

  function select(runId: string): void {
    selectedRunId.value = runId
  }

  async function create(topicId: string, input: CreateRunInput): Promise<Run> {
    const run = await api.createRun(topicId, input)
    runs.value = [run, ...runs.value]
    selectedRunId.value = run.id
    return run
  }

  function replace(run: Run): void {
    const index = runs.value.findIndex((item) => item.id === run.id)
    if (index >= 0) runs.value[index] = run
  }

  async function pause(runId: string): Promise<void> {
    const run = runs.value.find((item) => item.id === runId)
    if (!run) return
    const previous = run.state
    run.state = 'pausing'
    try {
      replace(await api.pauseRun(runId))
    } catch (err) {
      run.state = previous
      throw err
    }
  }

  async function resume(runId: string): Promise<void> {
    replace(await api.resumeRun(runId))
  }

  async function remove(runId: string): Promise<void> {
    await api.deleteRun(runId)
    runs.value = runs.value.filter((run) => run.id !== runId)
    if (selectedRunId.value === runId) {
      selectedRunId.value = runs.value[0]?.id ?? ''
    }
  }

  return {
    runs,
    selectedRunId,
    selectedRun,
    runningRun,
    loading,
    error,
    load,
    select,
    create,
    pause,
    resume,
    remove,
  }
})
