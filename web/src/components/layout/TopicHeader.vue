<script setup lang="ts">
import type { Topic, TopicBrief } from '@/types'
import IconButton from '@/components/ui/IconButton.vue'
import SegmentedControl from '@/components/ui/SegmentedControl.vue'
import ScopePopover from '@/components/report/ScopePopover.vue'

defineProps<{
  topic: Topic
  brief?: TopicBrief
  mode: 'report' | 'chat'
}>()

const emit = defineEmits<{
  back: []
  'update:mode': [mode: 'report' | 'chat']
}>()

const modes = [
  { value: 'report', label: 'Report' },
  { value: 'chat', label: 'Chat' },
]
</script>

<template>
  <header class="topbar">
    <div class="topbar__left">
      <IconButton label="Back to topics" @click="emit('back')">←</IconButton>
      <div class="topbar__title">
        <span class="topbar__eyebrow">Topic</span>
        <h1>{{ topic.direction }}</h1>
      </div>
      <ScopePopover :direction="topic.direction" :brief="brief" />
    </div>
    <SegmentedControl
      :model-value="mode"
      :options="modes"
      @update:model-value="emit('update:mode', $event as 'report' | 'chat')"
    />
  </header>
</template>

<style scoped>
.topbar {
  position: fixed;
  top: 0;
  right: 0;
  left: 0;
  z-index: 30;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  height: var(--topbar-h);
  padding: 0 var(--space-5);
  border-bottom: 1px solid var(--border);
  background: rgb(255 255 255 / 94%);
  backdrop-filter: blur(8px);
}

.topbar__left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
}

.topbar__title {
  min-width: 0;
}

.topbar__eyebrow {
  display: block;
  color: var(--text-faint);
  font-size: 10px;
  font-weight: 650;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.topbar__title h1 {
  overflow: hidden;
  font-size: 15px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
