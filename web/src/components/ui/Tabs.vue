<script setup lang="ts">
import type { TabItem } from '@/types'

defineProps<{
  tabs: TabItem[]
  activeId: string
  compact?: boolean
}>()

const emit = defineEmits<{
  select: [id: string]
  close: [id: string]
}>()
</script>

<template>
  <div class="tabs" :class="{ 'tabs--compact': compact }" role="tablist">
    <button
      v-for="tab in tabs"
      :key="tab.id"
      type="button"
      role="tab"
      class="tab"
      :class="{ 'tab--active': tab.id === activeId }"
      :aria-selected="tab.id === activeId"
      @click="emit('select', tab.id)"
    >
      <span class="tab__label">{{ tab.title }}</span>
      <span
        v-if="tab.closable"
        class="tab__close"
        role="button"
        aria-label="Close tab"
        @click.stop="emit('close', tab.id)"
      >×</span>
    </button>
  </div>
</template>

<style scoped>
.tabs {
  display: flex;
  align-items: stretch;
  gap: 2px;
  overflow-x: auto;
  border-bottom: 1px solid var(--border);
  scrollbar-width: thin;
}

.tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 180px;
  height: 34px;
  padding: 0 12px;
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--text-muted);
  font-size: 12px;
  white-space: nowrap;
}

.tab:hover {
  background: var(--surface-muted);
  color: var(--text);
}

.tab--active {
  border-bottom-color: var(--accent);
  color: var(--text);
  font-weight: 600;
}

.tab__label {
  overflow: hidden;
  text-overflow: ellipsis;
}

.tab__close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 3px;
  color: var(--text-faint);
  font-size: 15px;
  line-height: 1;
}

.tab__close:hover {
  background: var(--border);
  color: var(--text);
}

.tabs--compact .tab {
  height: 30px;
  padding: 0 9px;
}
</style>
