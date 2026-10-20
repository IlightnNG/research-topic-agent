<script setup lang="ts">
defineProps<{ title?: string; subtitle?: string; flat?: boolean }>();
</script>

<template>
  <section class="section-card" :class="{ flat }">
    <header v-if="title || $slots.actions" class="between">
      <div class="stack" style="gap: var(--space-1)">
        <h2 v-if="title" class="title-md">{{ title }}</h2>
        <p v-if="subtitle" class="muted">{{ subtitle }}</p>
      </div>
      <slot name="actions" />
    </header>
    <slot />
  </section>
</template>

<style scoped>
.section-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.section-card.flat {
  border: none;
  padding: 0;
  background: transparent;
}
</style>
