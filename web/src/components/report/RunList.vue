<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import type { Run } from '@/types'
import IconButton from '@/components/ui/IconButton.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'

defineProps<{
  runs: Run[]
  selectedId: string
  collapsed: boolean
  loading?: boolean
}>()

const emit = defineEmits<{
  select: [id: string]
  create: []
  delete: [run: Run]
  toggle: []
}>()

const menuFor = ref('')
const root = ref<HTMLElement | null>(null)

function onDocumentClick(event: MouseEvent): void {
  if (root.value && !root.value.contains(event.target as Node)) menuFor.value = ''
}

onMounted(() => document.addEventListener('click', onDocumentClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocumentClick))

function statusTone(state: Run['state']): 'neutral' | 'accent' | 'success' | 'warning' | 'danger' {
  if (state === 'succeeded') return 'success'
  if (state === 'running') return 'accent'
  if (state === 'paused' || state === 'pausing') return 'warning'
  if (state === 'failed') return 'danger'
  return 'neutral'
}

function timeAgo(iso: string): string {
  const minutes = Math.floor((Date.now() - new Date(iso).getTime()) / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

function onDelete(run: Run): void {
  menuFor.value = ''
  emit('delete', run)
}
</script>

<template>
  <aside ref="root" class="panel" :class="{ 'panel--collapsed': collapsed }">
    <header class="panel__head">
      <template v-if="!collapsed">
        <h2>Runs</h2>
        <div class="panel__actions">
          <IconButton label="New run" @click="emit('create')">+</IconButton>
          <IconButton label="Collapse runs" @click="emit('toggle')">‹</IconButton>
        </div>
      </template>
      <IconButton v-else label="Expand runs" @click="emit('toggle')">›</IconButton>
    </header>

    <div v-if="!collapsed" class="panel__body">
      <p v-if="loading" class="panel__state">Loading runs…</p>
      <p v-else-if="!runs.length" class="panel__state">No runs yet.</p>
      <ul v-else class="runs">
        <li v-for="run in runs" :key="run.id" class="run" :class="{ 'run--active': run.id === selectedId }">
          <button type="button" class="run__main" @click="emit('select', run.id)">
            <span class="run__title">{{ run.focus_hint || 'General direction' }}</span>
            <span class="run__meta">
              {{ timeAgo(run.created_at) }} · {{ run.language.toUpperCase() }}
            </span>
            <StatusBadge :tone="statusTone(run.state)">{{ run.state }}</StatusBadge>
          </button>
          <div class="run__menu">
            <button
              type="button"
              class="run__more"
              aria-label="Run actions"
              @click.stop="menuFor = menuFor === run.id ? '' : run.id"
            >⋯</button>
            <div v-if="menuFor === run.id" class="menu">
              <button type="button" @click.stop="onDelete(run)">Delete run</button>
            </div>
          </div>
        </li>
      </ul>
    </div>
    <div v-else class="rail">
      <button
        v-for="run in runs.slice(0, 6)"
        :key="run.id"
        type="button"
        class="rail__dot"
        :class="{ 'rail__dot--active': run.id === selectedId }"
        :title="run.focus_hint || run.id"
        @click="emit('select', run.id)"
      ></button>
    </div>
  </aside>
</template>

<style scoped>
.panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-right: 1px solid var(--border);
  background: var(--surface);
}

.panel--collapsed {
  align-items: center;
}

.panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  min-height: 48px;
  padding: 0 var(--space-3);
  border-bottom: 1px solid var(--border);
}

.panel__head h2 {
  font-size: 12px;
  font-weight: 650;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.panel__actions {
  display: flex;
  gap: 2px;
}

.panel__body {
  min-height: 0;
  overflow: auto;
  padding: var(--space-2);
}

.panel__state {
  padding: var(--space-3);
  color: var(--text-muted);
  font-size: 12px;
}

.runs {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.run {
  position: relative;
  display: flex;
  align-items: stretch;
  border-radius: var(--radius-sm);
}

.run:hover,
.run--active {
  background: var(--surface-muted);
}

.run__main {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: flex-start;
  gap: 3px;
  min-width: 0;
  padding: 8px 8px 8px 10px;
  border: 0;
  background: transparent;
  text-align: left;
}

.run__title {
  overflow: hidden;
  width: 100%;
  font-size: 12px;
  font-weight: 550;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.run__meta {
  color: var(--text-faint);
  font-size: 10px;
}

.run__menu {
  position: relative;
  display: flex;
  align-items: flex-start;
  padding-top: 4px;
}

.run__more {
  width: 24px;
  height: 24px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--text-faint);
}

.run__more:hover {
  background: var(--border);
  color: var(--text);
}

.menu {
  position: absolute;
  top: 28px;
  right: 0;
  z-index: 20;
  min-width: 120px;
  padding: 4px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  box-shadow: 0 8px 22px rgb(0 0 0 / 10%);
}

.menu button {
  width: 100%;
  padding: 7px 8px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--danger);
  font-size: 12px;
  text-align: left;
}

.menu button:hover {
  background: var(--danger-soft);
}

.rail {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 12px;
}

.rail__dot {
  width: 10px;
  height: 10px;
  padding: 0;
  border: 2px solid var(--border-strong);
  border-radius: 50%;
  background: var(--surface);
}

.rail__dot--active {
  border-color: var(--accent);
  background: var(--accent);
}
</style>
