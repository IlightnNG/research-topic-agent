<script setup lang="ts">
import { computed, ref } from "vue";

import type { Report, RunDetail, RunEvent, RunMetrics } from "@/api/types";

import { t } from "@/i18n";

import FailureCard from "./FailureCard.vue";
import ReportViewer from "./ReportViewer.vue";
import TrajectoryTimeline from "./TrajectoryTimeline.vue";

const props = defineProps<{
  run: RunDetail | null;
  events: RunEvent[];
  report: Report | null;
  reportError: string;
  view: "trajectory" | "report";
  highlightSeq: number | null;
  isRunning: boolean;
  isFailed: boolean;
  metrics?: RunMetrics | null;
}>();
const emit = defineEmits<{
  "update:view": ["trajectory" | "report"];
  abort: [];
  retry: [];
  why: [number];
  tabClick: [];
  pause: [];
  resume: [];
  inject: [string];
}>();

const costText = computed(() =>
  props.metrics?.cost_usd === undefined || props.metrics?.cost_usd === null
    ? ""
    : `$${Number(props.metrics.cost_usd).toFixed(4)}`,
);
const slowestText = computed(() => {
  const stage = props.metrics?.slowest_stage;
  if (!stage) return "";
  const ms = Number(props.metrics?.duration_by_stage?.[stage] ?? 0);
  return `${t("run.slowest")} ${stage} ${Math.round(ms)}ms`;
});

const injectOpen = ref(false);
const injectText = ref("");

function submitInject() {
  const text = injectText.value.trim();
  if (!text) return;
  emit("inject", text);
  injectText.value = "";
  injectOpen.value = false;
}

const tabs = ref(props.view);
</script>

<template>
  <div class="stack run-workspace">
    <div class="between">
      <el-tabs
        :model-value="view"
        class="grow"
        @update:model-value="
          (value) => {
            tabs = value as 'trajectory' | 'report';
            emit('update:view', tabs);
            emit('tabClick');
          }
        "
      >
        <el-tab-pane label="轨迹" name="trajectory" />
        <el-tab-pane label="报告" name="report" />
      </el-tabs>
      <div class="cluster">
        <el-tag v-if="run" size="small">{{ run.state }}</el-tag>
        <el-tag v-if="run?.period" size="small" type="info">{{ run.period }}</el-tag>
        <span v-if="costText" class="muted">{{ costText }}</span>
        <el-tag v-if="slowestText" size="small" type="info">{{ slowestText }}</el-tag>
        <el-button v-if="isRunning" size="small" text @click="emit('pause')">暂停</el-button>
        <el-button v-if="run?.state === 'paused'" size="small" type="primary" text @click="emit('resume')">
          继续
        </el-button>
        <el-button v-if="isRunning || run?.state === 'paused'" size="small" text @click="injectOpen = true">
          注入提示
        </el-button>
        <el-button v-if="isRunning" size="small" type="danger" text @click="emit('abort')">
          中止
        </el-button>
      </div>
    </div>

    <p class="sr-only" role="status" aria-live="polite">
      run {{ run?.id }} state {{ run?.state ?? "unknown" }}, events {{ events.length }}
    </p>

    <el-dialog v-model="injectOpen" title="注入提示词" width="420">
      <el-input v-model="injectText" placeholder="下一阶段将合并进 focus_hint" maxlength="500" />
      <template #footer>
        <el-button @click="injectOpen = false">取消</el-button>
        <el-button type="primary" @click="submitInject">注入</el-button>
      </template>
    </el-dialog>

    <template v-if="view === 'trajectory'">
      <FailureCard
        v-if="isFailed"
        :run="run"
        :error-code="run?.error_code"
        @retry="emit('retry')"
      />
      <TrajectoryTimeline :events="events" :highlight-seq="highlightSeq" />
    </template>

    <template v-else>
      <ReportViewer v-if="report" :report="report" @why="(index) => emit('why', index)" />
      <FailureCard
        v-else-if="isFailed"
        :run="run"
        :error-code="run?.error_code"
        @retry="emit('retry')"
      />
      <p v-else class="muted">{{ reportError || "报告尚未生成。" }}</p>
    </template>
  </div>
</template>

<style scoped>
.run-workspace {
  gap: var(--space-3);
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
