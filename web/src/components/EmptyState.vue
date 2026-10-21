<script setup lang="ts">
defineProps<{ title: string; hint?: string; compact?: boolean }>();
</script>

<template>
  <div class="empty stack" :class="{ compact }">
    <p class="title-md">{{ title }}</p>
    <p v-if="hint" class="muted">{{ hint }}</p>
    <div v-if="$slots.default" class="cluster">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.empty {
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: var(--space-6);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}
/* 侧栏内的紧凑空态：不抢主区视觉 */
.empty.compact {
  padding: var(--space-5) var(--space-4);
  margin: var(--space-3);
  border-style: none;
  background: transparent;
}
.empty.compact .title-md {
  font-size: var(--font-sm);
  font-weight: 600;
}
</style>
