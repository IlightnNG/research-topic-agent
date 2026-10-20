<script setup lang="ts">
import type { ReportSection } from "@/api/types";

defineProps<{ sections: ReportSection[] }>();
const emit = defineEmits<{ jump: [string] }>();
</script>

<template>
  <nav class="toc stack">
    <p class="muted">目录</p>
    <button v-for="section in sections" :key="section.id" class="toc-item" @click="emit('jump', section.id)">
      {{ section.title }}
    </button>
    <p v-if="!sections.length" class="muted">暂无章节</p>
  </nav>
</template>

<style scoped>
.toc {
  position: sticky;
  top: var(--space-4);
  align-self: start;
  gap: var(--space-1);
  width: 200px;
}
.toc-item {
  text-align: left;
  background: transparent;
  border: none;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--color-primary);
  font-size: var(--font-sm);
}
.toc-item:hover {
  background: var(--color-surface-soft);
}
</style>
