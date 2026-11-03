<script setup lang="ts">
import { computed } from 'vue'
import type { TraceEvent } from '@/types'

const props = defineProps<{ events: TraceEvent[] }>()

const sectionEvents = computed(() =>
  props.events.filter((event) => event.type === 'section.written'),
)
const latest = computed(() => sectionEvents.value[sectionEvents.value.length - 1])
const total = computed(() => latest.value?.total ?? 0)
const written = computed(() => latest.value?.written ?? 0)
const percentage = computed(() =>
  total.value ? Math.round((written.value / total.value) * 100) : 0,
)
</script>

<template>
  <div v-if="total" class="section-progress">
    <div class="section-progress__meta">
      <span>{{ written }} / {{ total }} sections</span>
      <span>{{ percentage }}%</span>
    </div>
    <div class="section-progress__bar" aria-hidden="true">
      <span :style="{ width: `${percentage}%` }"></span>
    </div>
  </div>
</template>

<style scoped>
.section-progress {
  margin: 8px 0 4px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface-raised);
}

.section-progress__meta {
  display: flex;
  justify-content: space-between;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
}

.section-progress__bar {
  height: 4px;
  margin-top: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--border);
}

.section-progress__bar span {
  display: block;
  height: 100%;
  background: var(--accent);
  transition: width 180ms ease;
}
</style>
