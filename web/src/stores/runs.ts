import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { describeError } from "@/api/client";
import { api } from "@/api/endpoints";
import type { Report, RunDetail, RunEvent, RunItem } from "@/api/types";

const TERMINAL = new Set(["succeeded", "failed", "aborted"]);

export const useRunsStore = defineStore("runs", () => {
  const items = ref<RunItem[]>([]);
  const current = ref<RunDetail | null>(null);
  const report = ref<Report | null>(null);
  const reportError = ref("");
  const events = ref<RunEvent[]>([]);
  const lastSeq = ref(0);
  const streaming = ref(false);
  const error = ref("");
  const userPinnedView = ref(false);

  const isRunning = computed(() =>
    ["queued", "running"].includes(current.value?.state ?? ""),
  );
  const isFailed = computed(() => ["failed", "aborted"].includes(current.value?.state ?? ""));

  async function loadList(topicId: string): Promise<void> {
    try {
      const page = await api.listRuns(topicId);
      items.value = page.items;
    } catch (err) {
      error.value = describeError(err);
    }
  }

  async function loadRun(runId: string): Promise<void> {
    current.value = await api.getRun(runId);
    await loadEvents(runId, 0);
  }

  /** 只刷新快照（轮询/重连用），不动事件列表 → 避免每 2s 全量重拉。 */
  async function loadSnapshot(runId: string): Promise<void> {
    current.value = await api.getRun(runId);
  }

  async function loadEvents(runId: string, afterSeq = 0): Promise<void> {
    const page = await api.listEvents(runId, afterSeq);
    const merged = new Map<number, RunEvent>();
    for (const event of [...events.value, ...page.items]) merged.set(event.seq, event);
    events.value = [...merged.values()].sort((a, b) => a.seq - b.seq);
    lastSeq.value = events.value.length ? events.value[events.value.length - 1]!.seq : afterSeq;
  }

  function mergeEvent(event: RunEvent): void {
    if (events.value.some((item) => item.seq === event.seq)) return;
    events.value = [...events.value, event].sort((a, b) => a.seq - b.seq);
    lastSeq.value = event.seq;
  }

  async function loadReport(runId: string): Promise<void> {
    report.value = null;
    reportError.value = "";
    try {
      report.value = await api.getReport(runId);
    } catch (err) {
      reportError.value = describeError(err);
    }
  }

  async function abort(runId: string): Promise<void> {
    await api.abortRun(runId);
  }

  async function triggerRun(
    topicId: string,
    body: { focus_hint?: string | null; wait?: boolean },
  ): Promise<{ run_id: string }> {
    return api.triggerRun(topicId, body);
  }

  function reset(): void {
    current.value = null;
    report.value = null;
    reportError.value = "";
    events.value = [];
    lastSeq.value = 0;
    userPinnedView.value = false;
  }

  return {
    items,
    current,
    report,
    reportError,
    events,
    lastSeq,
    streaming,
    error,
    userPinnedView,
    isRunning,
    isFailed,
    TERMINAL,
    loadList,
    loadRun,
    loadSnapshot,
    loadEvents,
    mergeEvent,
    loadReport,
    abort,
    triggerRun,
    reset,
  };
});
