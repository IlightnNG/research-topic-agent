<script setup lang="ts">
withDefaults(defineProps<{ sidebarWidth?: string }>(), { sidebarWidth: "var(--sidebar-w)" });
</script>

<template>
  <div class="two-pane" :style="{ '--pane-sidebar': sidebarWidth }">
    <aside class="pane-side">
      <slot name="side" />
    </aside>
    <section class="pane-main">
      <slot />
    </section>
  </div>
</template>

<style scoped>
.two-pane {
  display: grid;
  grid-template-columns: var(--pane-sidebar) minmax(0, 1fr);
  min-height: 0;
  flex: 1 1 auto;
}
.pane-side {
  border-right: 1px solid var(--color-border);
  background: var(--color-surface);
  overflow: auto;
}
.pane-main {
  overflow: auto;
  padding: var(--space-4) var(--space-5);
}
</style>
