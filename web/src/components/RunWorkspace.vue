<script setup lang="ts">
import { ref } from "vue";

import type { Report, RunDetail, RunEvent } from "@/api/types";

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
}>();
const emit = defineEmits<{
  "update:view": ["trajectory" | "report"];
  abort: [];
  retry: [];
  why: [number];
  tabClick: [];
}>();

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
        <el-button v-if="isRunning" size="small" type="danger" text @click="emit('abort')">
          中止
        </el-button>
      </div>
    </div>

    <p class="sr-only" role="status" aria-live="polite">
      run {{ run?.id }} state {{ run?.state ?? "unknown" }}, events {{ events.length }}
    </p>

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
