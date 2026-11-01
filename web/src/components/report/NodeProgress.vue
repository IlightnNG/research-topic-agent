<script setup lang="ts">
import { computed } from 'vue'
import type { NodeStatus, NodeTrace } from '@/types'

const props = defineProps<{
  nodes: NodeTrace[]
  currentId?: string
}>()

const committed = computed(() => props.nodes.filter((node) => node.status === 'committed').length)
const current = computed(
  () => props.nodes.find((node) => node.status === 'running' || node.status === 'verifying')?.node_id ?? props.currentId,
)
const percentage = computed(() =>
  props.nodes.length ? Math.round((committed.value / props.nodes.length) * 100) : 0,
)

function label(status: NodeStatus): string {
  return status.charAt(0).toUpperCase() + status.slice(1)
}
</script>

<template>
  <section class="progress">
    <div class="progress__meta">
      <span>{{ committed }} / {{ nodes.length }} nodes</span>
      <span v-if="current" class="progress__current">{{ current }}</span>
      <span class="progress__pct">{{ percentage }}%</span>
    </div>
    <div class="progress__bar" aria-hidden="true">
      <span
        v-for="node in nodes"
        :key="node.node_id"
        class="segment"
        :class="[`segment--${node.status}`, { 'segment--current': node.node_id === current }]"
        :title="`${node.title}: ${label(node.status)}`"
      ></span>
    </div>
    <div class="progress__labels">
      <span v-for="node in nodes" :key="node.node_id" class="progress__label">
        {{ node.title }}
        <em>{{ label(node.status) }}</em>
      </span>
    </div>
  </section>
</template>

<style scoped>
.progress {
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
}

.progress__meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  color: var(--text-muted);
  font-size: 11px;
}

.progress__current {
  color: var(--text);
  font-family: var(--font-mono);
}

.progress__pct {
  margin-left: auto;
  color: var(--text-faint);
}

.progress__bar {
  display: flex;
  gap: 4px;
  height: 5px;
  margin-top: 9px;
}

.segment {
  flex: 1;
  border-radius: 999px;
  background: var(--border);
}

.segment--committed {
  background: var(--success);
}

.segment--running,
.segment--verifying {
  background: var(--accent);
}

.segment--paused {
  background: var(--warning);
}

.segment--failed {
  background: var(--danger);
}

.segment--degraded {
  background: var(--warning);
}

.segment--skipped {
  background: var(--text-faint);
}

.segment--current {
  box-shadow: 0 0 0 3px var(--accent-soft);
}

.progress__labels {
  display: flex;
  gap: 4px;
  margin-top: 8px;
}

.progress__label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  color: var(--text-faint);
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress__label em {
  display: block;
  color: var(--text-faint);
  font-style: normal;
  font-size: 9px;
  text-transform: capitalize;
}
</style>
