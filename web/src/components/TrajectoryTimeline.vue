<script setup lang="ts">
import { computed, ref, watch } from "vue";

import type { RunEvent } from "@/api/types";

const props = defineProps<{ events: RunEvent[] }>();

const follow = ref(true);
const listEl = ref<HTMLElement | null>(null);

watch(
  () => props.events.length,
  () => {
    if (follow.value && listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight;
  },
);

const STAGES = ["intake", "ingest", "curate", "report"];

const stages = computed(() => {
  const done = new Set<string>();
  const started = new Set<string>();
  for (const event of props.events) {
    if (event.type !== "phase_change") continue;
    const phase = String((event.payload as { phase?: string }).phase ?? "");
    if (phase === "end") done.add(event.stage);
    if (phase === "start") started.add(event.stage);
  }
  const names = STAGES.filter((name) => done.has(name) || started.has(name));
  for (const name of done) if (!names.includes(name)) names.push(name);
  return names.map((name) => ({ name, done: done.has(name) }));
});

function severityOf(event: RunEvent): string {
  if (event.type === "error") return "error";
  if (event.type === "guard_trigger") return "warning";
  return "";
}

function summary(event: RunEvent): string {
  const p = event.payload as Record<string, unknown>;
  if (event.type === "phase_change") return String(p.phase ?? "");
  if (event.type === "guard_trigger") return `${p.code ?? ""} ${(p.reasons as string[] | undefined)?.[0] ?? ""}`.trim();
  if (event.type === "report_written") return `report ${p.report_id ?? ""} · claims ${p.claims ?? "?"}`;
  if (event.type === "error") return `${p.code ?? ""} ${p.message ?? ""}`.trim();
  if (event.type === "llm_call") return `${p.model ?? ""} · $${Number(p.cost ?? 0).toFixed(4)}`;
  if (event.type === "tool_call") return `${p.tool ?? ""} ${p.ok === false ? "failed" : "ok"}`;
  return "";
}
</script>

<template>
  <div class="stack">
    <div class="cluster">
      <el-tag v-for="stage in stages" :key="stage.name" size="small" :type="stage.done ? 'success' : 'info'">
        {{ stage.done ? "✓" : "•" }} {{ stage.name }}
      </el-tag>
      <el-switch v-model="follow" size="small" active-text="跟随" />
    </div>

    <ol ref="listEl" class="timeline">
      <li v-for="event in events" :key="event.seq" :class="severityOf(event)">
        <span class="seq mono">#{{ event.seq }}</span>
        <span class="type">{{ event.type }}</span>
        <span class="stage muted">{{ event.stage }}</span>
        <span class="summary">{{ summary(event) }}</span>
      </li>
    </ol>
    <p v-if="!events.length" class="muted">暂无事件。</p>
  </div>
</template>

<style scoped>
.timeline {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 60vh;
  overflow: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
}
.timeline li {
  display: grid;
  grid-template-columns: 56px 140px 96px 1fr;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--color-border);
  font-size: var(--font-sm);
  align-items: baseline;
}
.timeline li:last-child {
  border-bottom: none;
}
.timeline li.warning {
  background: color-mix(in srgb, var(--color-warning) 8%, transparent);
}
.timeline li.error {
  background: color-mix(in srgb, var(--color-danger) 8%, transparent);
}
.seq {
  color: var(--color-primary);
}
.type {
  font-weight: 600;
}
</style>
