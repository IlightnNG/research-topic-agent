import { ref } from 'vue'
import { defineStore } from 'pinia'
import type { RunTabState, TabItem } from '@/types'

const trajectoryTab: TabItem = {
  id: 'trajectory',
  kind: 'trajectory',
  title: 'Trajectory',
  closable: false,
}

export const useTabsStore = defineStore('runTabs', () => {
  const tabsByRun = ref<Record<string, RunTabState>>({})

  function ensureRun(runId: string, hasReport: boolean, reportTitle = 'Report'): RunTabState {
    const existing = tabsByRun.value[runId]
    if (!existing) {
      const tabs = [trajectoryTab]
      if (hasReport) {
        tabs.push({ id: 'report', kind: 'report', title: reportTitle, closable: false })
      }
      const state = {
        tabs: [...tabs],
        activeTabId: hasReport ? 'report' : 'trajectory',
      }
      tabsByRun.value[runId] = state
      return state
    }
    if (hasReport && !existing.tabs.some((tab) => tab.id === 'report')) {
      existing.tabs.push({ id: 'report', kind: 'report', title: reportTitle, closable: false })
    }
    if (!existing.tabs.some((tab) => tab.id === existing.activeTabId)) {
      existing.activeTabId = hasReport ? 'report' : 'trajectory'
    }
    return existing
  }

  function activeTab(runId: string): TabItem | undefined {
    const state = tabsByRun.value[runId]
    return state?.tabs.find((tab) => tab.id === state.activeTabId)
  }

  function tabs(runId: string): TabItem[] {
    return tabsByRun.value[runId]?.tabs ?? []
  }

  function activate(runId: string, tabId: string): void {
    const state = tabsByRun.value[runId]
    if (state?.tabs.some((tab) => tab.id === tabId)) state.activeTabId = tabId
  }

  function openPaper(runId: string, paperId: string, title: string): void {
    const state = tabsByRun.value[runId]
    if (!state) return
    const id = `paper:${paperId}`
    if (!state.tabs.some((tab) => tab.id === id)) {
      state.tabs.push({ id, kind: 'paper', title, closable: true, paperId })
    }
    state.activeTabId = id
  }

  function close(runId: string, tabId: string): void {
    const state = tabsByRun.value[runId]
    if (!state) return
    const tab = state.tabs.find((item) => item.id === tabId)
    if (!tab?.closable) return
    const index = state.tabs.findIndex((item) => item.id === tabId)
    state.tabs = state.tabs.filter((item) => item.id !== tabId)
    if (state.activeTabId === tabId) {
      state.activeTabId =
        state.tabs.find((item) => item.kind === 'report')?.id ??
        state.tabs.find((item) => item.kind === 'trajectory')?.id ??
        state.tabs[Math.max(0, index - 1)]?.id ??
        ''
    }
  }

  function resetRun(runId: string): void {
    delete tabsByRun.value[runId]
  }

  return { tabsByRun, ensureRun, activeTab, tabs, activate, openPaper, close, resetRun }
})
