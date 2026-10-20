<script setup lang="ts">
import { RouterLink, RouterView } from "vue-router";
</script>

<template>
  <div class="app-shell">
    <nav class="app-nav cluster">
      <RouterLink to="/topics" class="brand">lit-agent</RouterLink>
      <span class="muted">literature research assistant</span>
    </nav>
    <RouterView />
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  min-width: var(--layout-min-w);
}
.app-nav {
  padding: var(--space-3) var(--space-5);
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
}
.brand {
  font-weight: 700;
  color: var(--color-primary);
  text-decoration: none;
}
</style>
