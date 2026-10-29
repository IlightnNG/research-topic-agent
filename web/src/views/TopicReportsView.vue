<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import { describeError, httpErrorCode } from "@/api/client";
import EmptyState from "@/components/EmptyState.vue";
import ErrorBanner from "@/components/ErrorBanner.vue";
import GenerateReportDialog from "@/components/GenerateReportDialog.vue";
import RunList from "@/components/RunList.vue";
import RunWorkspace from "@/components/RunWorkspace.vue";
import TopicShell from "@/components/TopicShell.vue";
import { useRunSession } from "@/composables/useRunSession";
import { useTopicsStore } from "@/stores/topics";

const props = defineProps<{ runId?: string; topicId?: string }>();
const route = useRoute();
const topics = useTopicsStore();

const topicId = computed(() => props.topicId ?? String(route.params.topicId ?? ""));
const activeRunId = computed(() => props.runId ?? (route.params.runId as string | undefined) ?? null);

const session = useRunSession(topicId, activeRunId);
// 解构 ref 才能在模板里自动解包（`session.view` 不会）
const { runs, view, highlightSeq } = session;

const dialogOpen = ref(false);
const busy = ref(false);
const dialogError = ref("");

let lastLanguage: "en" | "zh" = "en";

async function generate(hint: string | null, language: "en" | "zh" = "en"): Promise<void> {
  lastLanguage = language;
  dialogError.value = "";
  busy.value = true;
  try {
    const result = await runs.triggerRun(topicId.value, {
      focus_hint: hint,
      wait: false,
      report_language: language,
    });
    dialogOpen.value = false;
    await runs.loadList(topicId.value);
    await session.openRun(result.run_id, true);
  } catch (err) {
    dialogError.value =
      httpErrorCode(err) === "E_LOCK_HELD"
        ? "This topic already has a running job; wait for it to finish"
        : describeError(err);
  } finally {
    busy.value = false;
  }
}

const retry = (): Promise<void> => generate(runs.current?.focus_hint ?? null, lastLanguage);

onMounted(async () => {
  session.applyUrlView();
  await topics.loadOne(topicId.value);
  await topics.load();
  await runs.loadList(topicId.value);
  if (activeRunId.value) {
    await session.refreshRun();
    return;
  }
  const latest = session.latestRunId.value;
  if (latest) await session.openRun(latest, true);
});
</script>

<template>
  <TopicShell
    :topic-id="topicId"
    :title="topics.current?.name ?? topicId"
    :subtitle="topics.current?.scope_statement ?? ''"
    active="report"
  >
    <template #actions>
      <el-button type="primary" @click="dialogOpen = true">Generate report</el-button>
    </template>

    <template #side>
      <div class="between pad-3">
        <strong>Runs</strong>
        <el-button size="small" type="primary" text @click="dialogOpen = true">+ Generate</el-button>
      </div>
      <RunList :items="runs.items" :active-id="activeRunId" @select="session.openRun" />
    </template>

    <div class="stack">
      <ErrorBanner
        v-if="runs.error"
        :message="runs.error"
        @retry="() => session.refreshRun(true)"
      />
      <EmptyState
        v-if="!activeRunId"
        compact
        title="No runs yet"
        hint="Click Generate report to start the first run."
      >
        <el-button type="primary" @click="dialogOpen = true">Generate first report</el-button>
      </EmptyState>

      <RunWorkspace
        v-else
        v-model:view="view"
        :run="runs.current"
        :events="runs.events"
        :report="runs.report"
        :report-error="runs.reportError"
        :metrics="runs.metrics"
        :highlight-seq="highlightSeq"
        :is-running="runs.isRunning"
        :is-failed="runs.isFailed"
        @tab-click="session.onTabClick"
        @abort="session.abort"
        @pause="session.pause"
        @resume="session.resume"
        @inject="session.inject"
        @retry="retry"
        @why="session.jumpToTrajectory"
      />
    </div>
  </TopicShell>

  <GenerateReportDialog
    v-model="dialogOpen"
    :busy="busy"
    :error-text="dialogError"
    @submit="generate"
  />
</template>
