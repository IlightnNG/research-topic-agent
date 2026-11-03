<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTopicsStore } from '@/stores/topics'
import { useRunsStore } from '@/stores/runs'
import { useTabsStore } from '@/stores/tabs'
import { useLayoutStore } from '@/stores/layout'
import { useTraceStore } from '@/stores/trace'
import { useReportsStore } from '@/stores/reports'
import { api } from '@/api/client'
import type { CreateRunInput, Run } from '@/types'
import TopicHeader from '@/components/layout/TopicHeader.vue'
import RunList from '@/components/report/RunList.vue'
import NewRunModal from '@/components/report/NewRunModal.vue'
import Tabs from '@/components/ui/Tabs.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import Button from '@/components/ui/Button.vue'
import TrajectoryTimeline from '@/components/report/TrajectoryTimeline.vue'
import ReportViewer from '@/components/report/ReportViewer.vue'
import PaperTab from '@/components/report/PaperTab.vue'
import InspectorPanel from '@/components/report/InspectorPanel.vue'

const route = useRoute()
const router = useRouter()
const topicsStore = useTopicsStore()
const runsStore = useRunsStore()
const tabsStore = useTabsStore()
const layout = useLayoutStore()
const traceStore = useTraceStore()
const reportsStore = useReportsStore()

const topicId = computed(() => String(route.params.topicId))
const topic = computed(() => topicsStore.byId[topicId.value])
const brief = computed(() => topicsStore.briefs[topicId.value])
const selected = computed(() => runsStore.selectedRun)
const tabs = computed(() => (selected.value ? tabsStore.tabs(selected.value.id) : []))
const activeTab = computed(() => (selected.value ? tabsStore.activeTab(selected.value.id) : undefined))
const trace = computed(() => (selected.value ? traceStore.traces[selected.value.id] : undefined))
const report = computed(() => (selected.value ? reportsStore.reports[selected.value.id] : undefined))

const newRunOpen = ref(false)
const busy = ref(false)
const createError = ref('')
const pendingDelete = ref<Run | null>(null)
const deleteBusy = ref(false)
const controlBusy = ref(false)
let unsubscribe: (() => void) | undefined

onMounted(async () => {
  if (!topicsStore.topics.length) await topicsStore.load()
  if (!topic.value) return
  await Promise.all([runsStore.load(topicId.value), topicsStore.loadBrief(topicId.value)])
  selectInitialRun()
})

onBeforeUnmount(() => {
  unsubscribe?.()
})

watch(
  () => selected.value?.id,
  (id) => {
    if (!id) return
    const run = runsStore.runs.find((item) => item.id === id)
    if (run) tabsStore.ensureRun(run.id, Boolean(run.report_id))
    if (route.query.run !== id) void router.replace({ query: { ...route.query, run: id } })
    if (id) {
      unsubscribe?.()
      void traceStore.load(id)
      if (run?.report_id) void reportsStore.load(id)
      unsubscribe = api.subscribeRunEvents(id, (event) => handleRunEvent(id, event))
    }
  },
)

function handleRunEvent(id: string, event: Parameters<Parameters<typeof api.subscribeRunEvents>[1]>[0]): void {
  traceStore.append(id, event)
  if (event.type === 'run.failed') {
    void runsStore.load(topicId.value).then(() => {
      runsStore.select(id)
      const next = runsStore.runs.find((item) => item.id === id)
      if (next) tabsStore.ensureRun(next.id, Boolean(next.report_id))
    })
    void traceStore.load(id)
    return
  }
  if (event.type === 'run.finished' || event.type === 'run.paused' || event.type === 'run.resumed') {
    void runsStore.load(topicId.value).then(() => {
      runsStore.select(id)
      const next = runsStore.runs.find((item) => item.id === id)
      if (next) tabsStore.ensureRun(next.id, Boolean(next.report_id))
    })
    if (event.type === 'run.finished') void reportsStore.load(id, true)
  }
}

function selectInitialRun(): void {
  const queryRun = String(route.query.run || '')
  const run = runsStore.runs.find((item) => item.id === queryRun) || runsStore.runs[0]
  if (run) selectRun(run.id)
}

function selectRun(runId: string): void {
  runsStore.select(runId)
  const run = runsStore.runs.find((item) => item.id === runId)
  if (run) tabsStore.ensureRun(run.id, Boolean(run.report_id))
}

async function createRun(input: CreateRunInput): Promise<void> {
  busy.value = true
  createError.value = ''
  try {
    const run = await runsStore.create(topicId.value, input)
    tabsStore.ensureRun(run.id, false)
    newRunOpen.value = false
    await router.replace({ query: { ...route.query, run: run.id } })
    await traceStore.load(run.id)
  } catch (error) {
    createError.value = error instanceof Error ? error.message : 'Could not create run.'
  } finally {
    busy.value = false
  }
}

async function confirmDelete(): Promise<void> {
  if (!pendingDelete.value) return
  deleteBusy.value = true
  try {
    const runId = pendingDelete.value.id
    await runsStore.remove(runId)
    tabsStore.resetRun(runId)
    pendingDelete.value = null
    const next = runsStore.runs[0]
    if (next) {
      selectRun(next.id)
    } else {
      await router.replace({ query: { ...route.query, run: undefined } })
    }
  } finally {
    deleteBusy.value = false
  }
}

async function pauseRun(): Promise<void> {
  if (!selected.value) return
  controlBusy.value = true
  try {
    await runsStore.pause(selected.value.id)
    await traceStore.load(selected.value.id)
  } finally {
    controlBusy.value = false
  }
}

async function resumeRun(): Promise<void> {
  if (!selected.value) return
  controlBusy.value = true
  try {
    await runsStore.resume(selected.value.id)
    await traceStore.load(selected.value.id)
    unsubscribe?.()
    unsubscribe = api.subscribeRunEvents(selected.value.id, (event) =>
      handleRunEvent(selected.value!.id, event),
    )
  } finally {
    controlBusy.value = false
  }
}

async function retrySection(sectionId: string): Promise<void> {
  if (!selected.value) return
  controlBusy.value = true
  try {
    await api.retrySection(selected.value.id, sectionId)
    await Promise.all([
      traceStore.load(selected.value.id),
      reportsStore.load(selected.value.id, true),
      runsStore.load(topicId.value),
    ])
    runsStore.select(selected.value.id)
  } catch (error) {
    createError.value = error instanceof Error ? error.message : 'Could not retry section.'
  } finally {
    controlBusy.value = false
  }
}

async function openPaper(paperId: string): Promise<void> {
  if (!selected.value) return
  const paper = await api.getPaper(paperId)
  tabsStore.openPaper(selected.value.id, paperId, paper?.title || 'Paper')
}

function switchMode(mode: 'report' | 'chat'): void {
  void router.push(`/topics/${topicId.value}/${mode}`)
}
</script>

<template>
  <div v-if="topic" class="report-page">
    <TopicHeader
      :topic="topic"
      :brief="brief"
      mode="report"
      @back="router.push('/')"
      @update:mode="switchMode"
    />

    <div
      class="workspace"
      :style="{
        gridTemplateColumns: `${layout.leftWidth}px minmax(0, 1fr) ${layout.rightCollapsed ? '44px' : '300px'}`,
      }"
    >
      <RunList
        :runs="runsStore.runs"
        :selected-id="runsStore.selectedRunId"
        :collapsed="layout.leftCollapsed"
        :loading="runsStore.loading"
        @select="selectRun"
        @create="newRunOpen = true"
        @delete="pendingDelete = $event"
        @toggle="layout.toggleLeft"
      />

      <main class="main">
        <template v-if="selected">
          <Tabs
            :tabs="tabs"
            :active-id="activeTab?.id || ''"
            compact
            @select="tabsStore.activate(selected.id, $event)"
            @close="tabsStore.close(selected.id, $event)"
          />
          <div class="main__content">
            <TrajectoryTimeline
              v-if="activeTab?.kind === 'trajectory'"
              :run="selected"
              :trace="trace"
              :loading="traceStore.loading[selected.id]"
              :error="traceStore.error[selected.id]"
              :busy="controlBusy"
              @pause="pauseRun"
              @resume="resumeRun"
              @retry-section="retrySection"
            />
            <ReportViewer
              v-else-if="activeTab?.kind === 'report' && report"
              :report="report"
              @open-paper="openPaper"
            />
            <div v-else-if="activeTab?.kind === 'report'" class="report-state">
              <p v-if="reportsStore.loading[selected.id]">Loading report…</p>
              <EmptyState
                v-else
                title="Report not ready"
                :description="reportsStore.error[selected.id] || 'The report will appear here when the run completes.'"
              />
            </div>
            <PaperTab v-else-if="activeTab?.kind === 'paper' && activeTab.paperId" :paper-id="activeTab.paperId" />
          </div>
        </template>

        <div v-else class="main__empty">
          <EmptyState
            title="No run selected"
            description="Create a report run to start a trajectory for this topic."
          >
            <Button variant="primary" size="sm" @click="newRunOpen = true">New Report Run</Button>
          </EmptyState>
        </div>
      </main>

      <InspectorPanel
        :collapsed="layout.rightCollapsed"
        :report="report"
        @toggle="layout.toggleRight"
        @open-paper="openPaper"
      />
    </div>

    <NewRunModal
      :open="newRunOpen"
      :busy="busy"
      :error="createError"
      @close="newRunOpen = false"
      @create="createRun"
    />

    <ConfirmDialog
      :open="Boolean(pendingDelete)"
      title="Delete this run?"
      message="This removes the run, its trace, report, and paper tabs. If the run is active, it will be stopped first."
      confirm-text="Delete run"
      :busy="deleteBusy"
      @cancel="pendingDelete = null"
      @confirm="confirmDelete"
    />
  </div>

  <div v-else class="missing">
    <EmptyState title="Topic not found" description="This topic no longer exists or could not be loaded.">
      <Button size="sm" @click="router.push('/')">Back to topics</Button>
    </EmptyState>
  </div>
</template>

<style scoped>
.report-page {
  height: 100%;
  padding-top: var(--topbar-h);
}

.workspace {
  display: grid;
  height: calc(100vh - var(--topbar-h));
  min-height: 0;
}

.main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  background: var(--bg);
}

.main__content {
  flex: 1;
  min-height: 0;
  overflow: auto;
  background: var(--surface);
}

.main__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  background: var(--surface);
}

.report-state {
  padding: 24px;
}

.missing {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding-top: var(--topbar-h);
}
</style>
