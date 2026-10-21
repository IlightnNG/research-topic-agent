<script setup lang="ts">
import { ArrowLeft } from "@element-plus/icons-vue";
import { useRouter } from "vue-router";

const props = defineProps<{
  title: string;
  subtitle?: string;
  backTo?: string;
  backLabel?: string;
}>();

const router = useRouter();

function goBack(): void {
  if (props.backTo) void router.push(props.backTo);
}
</script>

<template>
  <header class="between page-header" :class="{ 'with-back': backTo }">
    <div class="cluster head-main">
      <button v-if="backTo" type="button" class="back-rail" @click="goBack">
        <el-icon><ArrowLeft /></el-icon>
        <span>{{ backLabel ?? "Back" }}</span>
      </button>
      <div class="stack head-text">
        <h1 class="title-md">{{ title }}</h1>
        <p v-if="subtitle" class="muted truncate">{{ subtitle }}</p>
      </div>
    </div>
    <div class="cluster">
      <slot name="actions" />
    </div>
  </header>
</template>

<style scoped>
.page-header {
  padding: var(--space-3) var(--space-5);
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  min-height: 64px;
}
.page-header.with-back {
  padding-left: 0;
}
.head-main {
  gap: var(--space-4);
  min-width: 0;
}
.head-text {
  gap: var(--space-1);
  min-width: 0;
}
/* 贴住顶栏、撑满高度的返回栏（视觉上与顶框等高，右侧一条分隔线） */
.back-rail {
  align-self: stretch;
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  height: auto;
  padding: 0 var(--space-4);
  border: none;
  border-right: 1px solid var(--color-border);
  border-radius: 0;
  background: transparent;
  color: var(--color-text-muted);
  font: inherit;
  font-size: var(--font-sm);
  cursor: pointer;
  transition: background 120ms ease, color 120ms ease;
}
.back-rail:hover {
  background: var(--color-surface-soft);
  color: var(--color-primary);
}
.back-rail:active {
  background: color-mix(in srgb, var(--color-primary) 10%, transparent);
}
</style>
