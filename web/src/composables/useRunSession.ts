import { ElMessage } from "element-plus";
import { computed, onBeforeUnmount, ref, watch } from "vue";
import type { ComputedRef, Ref } from "vue";
import { useRouter } from "vue-router";

import { describeError } from "@/api/client";
import { api as endpoints } from "@/api/endpoints";
import { useSse } from "@/composables/useSse";
import { useRunsStore } from "@/stores/runs";

/** run 会话逻辑：加载/轮询/SSE/视图决策/高亮。页面只负责渲染。 */
export function useRunSession(topicId: Ref<string>, activeRunId: ComputedRef<string | null>) {
  const router = useRouter();
  const runs = useRunsStore();
  const view = ref<"trajectory" | "report">("trajectory");
  const highlightSeq = ref<number | null>(null);

  const sse = useSse(() => activeRunId.value, {
    onEvent: (event) => runs.mergeEvent(event),
    onDone: () => void refreshRun(false),
    getSeq: () => runs.lastSeq,
  });

  let poller: number | null = null;

  function startPolling(): void {
    stopPolling();
    poller = window.setInterval(async () => {
      if (!runs.isRunning || !activeRunId.value) {
        stopPolling();
        if (!runs.isRunning) await refreshRun(false);
        return;
      }
      await refreshRun(false);
    }, 2000);
  }

  function stopPolling(): void {
    if (poller !== null) {
      window.clearInterval(poller);
      poller = null;
    }
  }

  onBeforeUnmount(stopPolling);

  function decideView(): void {
    if (runs.userPinnedView && view.value === "trajectory") return;
    if ((runs.current?.state ?? "") === "succeeded") {
      view.value = "report";
      if (!runs.report && activeRunId.value) void runs.loadReport(activeRunId.value);
    } else {
      view.value = "trajectory";
    }
  }

  async function refreshRun(full = true): Promise<void> {
    const runId = activeRunId.value;
    if (!runId) return;
    try {
      if (full || !runs.current) await runs.loadRun(runId);
      else await runs.loadSnapshot(runId);
      decideView();
      if (!runs.isRunning && !runs.metrics) {
        void runs.loadMetrics(runId);
      }
      if (runs.isRunning) {
        runs.streaming = true;
        sse.start(runs.lastSeq);
        startPolling();
      } else {
        stopPolling();
        // run 进入终态后刷新左侧列表，避免"头部 succeeded、列表还 running"
        void runs.loadList(topicId.value);
      }
    } catch (err) {
      runs.error = describeError(err);
    }
  }

  async function openRun(runId: string, auto = false): Promise<void> {
    runs.reset();
    runs.userPinnedView = !auto;
    await router.push({ name: "run", params: { topicId: topicId.value, runId } });
    await refreshRun();
  }

  /** 只有**真实点击**才置位；程序化切换（自动落报告）不算。 */
  function onTabClick(): void {
    runs.userPinnedView = true;
    if (view.value === "report" && activeRunId.value && !runs.report) {
      void runs.loadReport(activeRunId.value);
    }
  }

  async function abort(): Promise<void> {
    if (activeRunId.value) await runs.abort(activeRunId.value);
  }

  function jumpToTrajectory(claimIndex: number): void {
    const target =
      [...runs.events]
        .reverse()
        .find(
          (event) =>
            event.stage === "report" &&
            (event.type === "report_written" ||
              (event.type === "phase_change" &&
                String((event.payload as { phase?: string }).phase ?? "") === "end")),
        ) ?? runs.events[runs.events.length - 1];
    highlightSeq.value = target ? target.seq : null;
    runs.userPinnedView = true;
    view.value = "trajectory";
    ElMessage.info(target ? `claim #${claimIndex + 1} ← 事件 #${target.seq}` : "没有可定位的事件");
  }

  watch(view, (value) => {
    void router.replace({ query: { ...router.currentRoute.value.query, view: value } });
  });

  function applyUrlView(): void {
    const raw = router.currentRoute.value.query.view;
    if (raw === "report" || raw === "trajectory") {
      view.value = raw;
      runs.userPinnedView = true;
    }
  }

  /** 干预（Phase 2 / S12）：暂停 / 继续 / 注入。 */
  async function pause(): Promise<void> {
    if (!activeRunId.value) return;
    await endpoints.pauseRun(activeRunId.value);
    await refreshRun(false);
  }

  async function resume(): Promise<void> {
    if (!activeRunId.value) return;
    await endpoints.resumeRun(activeRunId.value);
    await refreshRun(false);
  }

  async function inject(prompt: string): Promise<void> {
    if (!activeRunId.value) return;
    await endpoints.injectRun(activeRunId.value, prompt);
  }

  return {
    pause,
    resume,
    inject,
    runs,
    view,
    highlightSeq,
    openRun,
    refreshRun,
    onTabClick,
    abort,
    jumpToTrajectory,
    applyUrlView,
    stopPolling,
    latestRunId: computed(() => runs.items[0]?.id ?? null),
  };
}
