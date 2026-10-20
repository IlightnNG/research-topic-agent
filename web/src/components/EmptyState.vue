<script setup lang="ts">
defineProps<{ title: string; hint?: string }>();
</script>

<template>
  <div class="empty stack">
    <p class="title-md">{{ title }}</p>
    <p v-if="hint" class="muted">{{ hint }}</p>
    <div class="cluster">
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
</style>
