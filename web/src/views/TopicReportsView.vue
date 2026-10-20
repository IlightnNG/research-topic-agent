<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
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
  runs.userPinnedView = true;
  void router.replace({ query: { ...route.query, view: value } });
});

async function openRun(runId: string, auto = false): Promise<void> {
  runs.reset();
  await router.push({ name: "run", params: { topicId: topicId.value, runId } });
  if (auto) runs.userPinnedView = false;
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
    }
  } catch (err) {
    runs.error = describeError(err);
  }
}

function decideView(): void {
  const state = runs.current?.state ?? "";
  if (runs.userPinnedView) return;
  if (state === "succeeded") {
    view.value = "report";
    void runs.loadReport(activeRunId.value!);
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
            <el-tabs v-model="view" class="grow">
              <el-tab-pane label="轨迹" name="trajectory" />
              <el-tab-pane label="报告" name="report" />
            </el-tabs>
            <div class="cluster">
              <el-tag v-if="runs.current" size="small">{{ runs.current.state }}</el-tag>
              <el-tag v-if="runs.current?.period" size="small" type="info">{{ runs.current.period }}</el-tag>
              <el-button v-if="runs.isRunning" size="small" type="danger" text @click="abort">中止</el-button>
            </div>
          </div>

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
</style>
