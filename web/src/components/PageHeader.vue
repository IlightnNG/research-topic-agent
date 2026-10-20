<script setup lang="ts">
defineProps<{
  title: string;
  subtitle?: string;
  backTo?: string;
  backLabel?: string;
}>();
</script>

<template>
  <header class="between page-header">
    <div class="stack" style="gap: var(--space-1)">
      <div class="cluster">
        <RouterLink v-if="backTo" :to="backTo" class="back">{{ backLabel ?? "Back" }}</RouterLink>
        <h1 class="title-md">{{ title }}</h1>
      </div>
      <p v-if="subtitle" class="muted truncate">{{ subtitle }}</p>
    </div>
    <div class="cluster">
      <slot name="actions" />
    </div>
  </header>
</template>

<style scoped>
.page-header {
  padding: var(--space-4) var(--space-5);
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
}
.back {
  color: var(--color-primary);
  text-decoration: none;
  font-size: var(--font-sm);
}
</style>
