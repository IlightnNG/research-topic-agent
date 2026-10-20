<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { describeError, httpErrorCode } from "@/api/client";
import ErrorBanner from "@/components/ErrorBanner.vue";
import FailureCard from "@/components/FailureCard.vue";
import GenerateReportDialog from "@/components/GenerateReportDialog.vue";
import PageHeader from "@/components/PageHeader.vue";
import ReportViewer from "@/components/ReportViewer.vue";
import RunList from "@/components/RunList.vue";
import TrajectoryTimeline from "@/components/TrajectoryTimeline.vue";
import TwoPaneLayout from "@/components/TwoPaneLayout.vue";
import { useSse } from "@/composables/useSse";
import { useRunsStore } from "@/stores/runs";
import { useTopicsStore } from "@/stores/topics";

const props = defineProps<{ runId?: string; topicId?: string }>();
const route = useRoute();
const router = useRouter();
const topics = useTopicsStore();
const runs = useRunsStore();

const topicId = computed(() => props.topicId ?? String(route.params.topicId ?? ""));
const activeRunId = computed(() => props.runId ?? (route.params.runId as string | undefined) ?? null);
const view = ref<"trajectory" | "report">("trajectory");
const dialogOpen = ref(false);
const busy = ref(false);
const dialogError = ref("");
const sse = useSse(() => activeRunId.value, {
  onEvent: (event) => runs.mergeEvent(event),
  onDone: () => void refreshRun(),
});

watch(
  () => route.query.view,
  (value) => {
    if (value === "report" || value === "trajectory") view.value = value;
  },
  { immediate: true },
);

watch(view, (value) => {
  void router.replace({ query: { ...route.query, view: value } });
});

/** 只有**用户点击** tab 才算"钉住视图"；程序化切换（自动落报告）不算。 */
function onTabClick(): void {
  // 只有**真实点击**才置位（此前误写在 watch(view) 里，导致自动切换也被当成"手动" → 报告永不加载）
  runs.userPinnedView = true;
  if (view.value === "report" && activeRunId.value && !runs.report) {
    void runs.loadReport(activeRunId.value);
  }
}

/** SSE 之外的兜底：运行中每 2s 轮询状态，终态即刷新并决定视图。 */
let poller: number | null = null;
function startPolling(): void {
  stopPolling();
  poller = window.setInterval(async () => {
    if (!runs.isRunning || !activeRunId.value) {
      stopPolling();
      if (!runs.isRunning) await refreshRun();
      return;
    }
    await refreshRun();
  }, 2000);
}
function stopPolling(): void {
  if (poller !== null) {
    window.clearInterval(poller);
    poller = null;
  }
}
onBeforeUnmount(stopPolling);

async function openRun(runId: string, auto = false): Promise<void> {
  runs.reset();
  runs.userPinnedView = !auto; // 手动选择某个 run → 尊重用户的视图偏好；自动跳转则恢复默认
  await router.push({ name: "run", params: { topicId: topicId.value, runId } });
  await refreshRun();
}

async function refreshRun(): Promise<void> {
  const runId = activeRunId.value;
  if (!runId) return;
  try {
    await runs.loadRun(runId);
    decideView();
    if (runs.isRunning) {
      runs.streaming = true;
      sse.start(runs.lastSeq);
      startPolling();
    } else {
      stopPolling();
    }
  } catch (err) {
    runs.error = describeError(err);
  }
}

function decideView(): void {
  // 用户**手动点过 tab** 之后，不再自动改视图（否则轮询每 2s 会把用户弹回去 → 批次1 / E）
  if (runs.userPinnedView && view.value === "trajectory") return;
  const state = runs.current?.state ?? "";
  if (state === "succeeded") {
    view.value = "report";
    if (!runs.report) void runs.loadReport(activeRunId.value!);
  } else {
    view.value = "trajectory";
  }
}

async function generate(hint: string | null): Promise<void> {
  dialogError.value = "";
  busy.value = true;
  try {
    const result = await runs.triggerRun(topicId.value, { focus_hint: hint, wait: false });
    dialogOpen.value = false;
    await runs.loadList(topicId.value);
    await openRun(result.run_id, true);
  } catch (err) {
    dialogError.value =
      httpErrorCode(err) === "E_LOCK_HELD" ? "该 topic 已有任务在运行，请等它结束" : describeError(err);
  } finally {
    busy.value = false;
  }
}

async function retry(): Promise<void> {
  await generate(runs.current?.focus_hint ?? null);
}

async function abort(): Promise<void> {
  if (activeRunId.value) await runs.abort(activeRunId.value);
}

function jumpToTrajectory(): void {
  runs.userPinnedView = false;
  view.value = "trajectory";
}

onMounted(async () => {
  await topics.loadOne(topicId.value);
  await runs.loadList(topicId.value);
  if (activeRunId.value) {
    await refreshRun();
    return;
  }
  const latest = runs.items[0];
  if (latest) await openRun(latest.id, true);
});
</script>

<template>
  <div class="page stack">
    <PageHeader
      :title="topics.current?.name ?? topicId"
      :subtitle="topics.current?.scope_statement ?? ''"
      back-to="/topics"
      back-label="Topics"
    >
      <template #actions>
        <el-button type="primary" @click="dialogOpen = true">生成新周报</el-button>
        <el-button @click="router.push({ name: 'topic-chat', params: { topicId } })">Chat</el-button>
      </template>
    </PageHeader>

    <TwoPaneLayout>
      <template #side>
        <div class="between" style="padding: var(--space-3)">
          <strong>Runs</strong>
          <el-button size="small" type="primary" text @click="dialogOpen = true">+ 生成</el-button>
        </div>
        <RunList :items="runs.items" :active-id="activeRunId" @select="openRun" />
      </template>

      <div class="stack">
        <ErrorBanner v-if="runs.error" :message="runs.error" @retry="refreshRun" />
        <p v-if="!activeRunId" class="muted">选择左侧的运行记录，或生成一份新周报。</p>

        <template v-else>
          <div class="between">
            <el-tabs v-model="view" class="grow" @tab-click="onTabClick">
              <el-tab-pane label="轨迹" name="trajectory" />
              <el-tab-pane label="报告" name="report" />
            </el-tabs>
            <div class="cluster">
              <el-tag v-if="runs.current" size="small">{{ runs.current.state }}</el-tag>
              <el-tag v-if="runs.current?.period" size="small" type="info">{{ runs.current.period }}</el-tag>
              <el-button v-if="runs.isRunning" size="small" type="danger" text @click="abort">中止</el-button>
            </div>
          </div>

          <p class="sr-only" role="status" aria-live="polite">
            run {{ activeRunId }} state {{ runs.current?.state ?? "unknown" }}, events {{ runs.events.length }}
          </p>

          <template v-if="view === 'trajectory'">
            <FailureCard
              v-if="runs.isFailed"
              :run="runs.current"
              :error-code="runs.current?.error_code"
              @retry="retry"
            />
            <TrajectoryTimeline :events="runs.events" />
          </template>

          <template v-else>
            <ReportViewer
              v-if="runs.report"
              :report="runs.report"
              @why="jumpToTrajectory"
            />
            <FailureCard
              v-else-if="runs.isFailed"
              :run="runs.current"
              :error-code="runs.current?.error_code"
              @retry="retry"
            />
            <p v-else class="muted">{{ runs.reportError || "报告尚未生成。" }}</p>
          </template>
        </template>
      </div>
    </TwoPaneLayout>

    <GenerateReportDialog
      v-model="dialogOpen"
      :busy="busy"
      :error-text="dialogError"
      @submit="generate"
    />
  </div>
</template>

<style scoped>
.page {
  height: calc(100vh - 49px);
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}
</style>
