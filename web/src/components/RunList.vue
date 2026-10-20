<script setup lang="ts">
import type { RunItem } from "@/api/types";

import StatusBadge from "./StatusBadge.vue";

defineProps<{ items: RunItem[]; activeId?: string | null }>();
const emit = defineEmits<{ select: [string] }>();

function period(run: RunItem): string {
  return run.period ?? "—";
}

function duration(run: RunItem): string {
  if (!run.started_at || !run.finished_at) return "";
  const ms = Date.parse(run.finished_at) - Date.parse(run.started_at);
  return ms > 0 ? `${(ms / 1000).toFixed(1)}s` : "";
}
</script>

<template>
  <ul class="run-list">
    <li
      v-for="run in items"
      :key="run.id"
      :class="{ active: run.id === activeId }"
      @click="emit('select', run.id)"
    >
      <div class="between">
        <strong class="mono">{{ period(run) }}</strong>
        <StatusBadge :state="run.state" />
      </div>
      <div class="cluster muted">
        <span v-if="run.stage">stage {{ run.stage }}</span>
        <span v-if="duration(run)">{{ duration(run) }}</span>
        <span>${{ Number(run.cost_usd ?? 0).toFixed(4) }}</span>
        <StatusBadge v-if="run.report_id" state="ok" label="报告" />
        <StatusBadge v-else-if="run.state === 'succeeded'" state="archived" label="无报告" />
      </div>
      <p v-if="run.focus_hint" class="muted truncate">🎯 {{ run.focus_hint }}</p>
    </li>
  </ul>
  <p v-if="!items.length" class="muted" style="padding: var(--space-4)">还没有运行记录。</p>
</template>

<style scoped>
.run-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.run-list li {
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.run-list li:hover {
  background: var(--color-surface-soft);
}
.run-list li.active {
  background: color-mix(in srgb, var(--color-primary) 10%, transparent);
  box-shadow: inset 3px 0 0 var(--color-primary);
}
</style>
