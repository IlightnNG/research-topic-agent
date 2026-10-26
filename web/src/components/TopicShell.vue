<script setup lang="ts">
import { useRouter } from "vue-router";

import PageHeader from "./PageHeader.vue";
import TwoPaneLayout from "./TwoPaneLayout.vue";

const props = defineProps<{
  topicId: string;
  title?: string;
  subtitle?: string;
  active: "report" | "chat";
}>();

const router = useRouter();

function go(name: "topic-reports" | "topic-chat"): void {
  if (name === "topic-reports" && props.active === "report") return;
  if (name === "topic-chat" && props.active === "chat") return;
  void router.push({ name, params: { topicId: props.topicId } });
}
</script>

<template>
  <div class="topic-shell stack">
    <PageHeader
      :title="title ?? topicId"
      :subtitle="subtitle"
      back-to="/topics"
      back-label="Topics"
    >
      <template #actions>
        <slot name="actions" />
        <nav class="page-switch" aria-label="Page switch">
          <button
            type="button"
            class="switch-item"
            :class="{ current: active === 'report' }"
            :aria-current="active === 'report' ? 'page' : undefined"
            @click="go('topic-reports')"
          >
            Report
          </button>
          <button
            type="button"
            class="switch-item"
            :class="{ current: active === 'chat' }"
            :aria-current="active === 'chat' ? 'page' : undefined"
            @click="go('topic-chat')"
          >
            Chat
          </button>
        </nav>
      </template>
    </PageHeader>

    <TwoPaneLayout>
      <template #side>
        <slot name="side" />
      </template>
      <slot />
    </TwoPaneLayout>
  </div>
</template>

<style scoped>
.topic-shell {
  height: calc(100vh - 49px);
  gap: 0;
}
.page-switch {
  display: inline-flex;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}
.switch-item {
  border: none;
  background: transparent;
  color: var(--color-text);
  font: inherit;
  font-size: var(--font-sm);
  padding: var(--space-2) var(--space-4);
  cursor: pointer;
  transition: background 120ms ease, color 120ms ease;
}
.switch-item + .switch-item {
  border-left: 1px solid var(--color-border);
}
.switch-item:hover {
  color: var(--color-primary);
  background: var(--color-surface-soft);
}
.switch-item.current {
  background: color-mix(in srgb, var(--color-primary) 12%, transparent);
  color: var(--color-primary);
  font-weight: 600;
  cursor: default;
}
</style>
