<script setup lang="ts">
import { computed, ref } from 'vue'
import type { PaperLink, Report } from '@/types'
import IconButton from '@/components/ui/IconButton.vue'

const props = defineProps<{
  collapsed: boolean
  report?: Report
}>()

const emit = defineEmits<{
  toggle: []
  openPaper: [paperId: string]
}>()

const tab = ref<'citations' | 'authors'>('citations')

const citations = computed<PaperLink[]>(() => {
  const seen = new Set<string>()
  const items: PaperLink[] = []
  for (const section of props.report?.sections ?? []) {
    for (const link of section.paper_links ?? []) {
      const key = `${link.paper_id}:${link.token}`
      if (seen.has(key)) continue
      seen.add(key)
      items.push(link)
    }
  }
  return items
})
</script>

<template>
  <aside class="inspector" :class="{ 'inspector--collapsed': collapsed }">
    <header class="inspector__head">
      <IconButton v-if="!collapsed" label="Collapse inspector" @click="emit('toggle')">›</IconButton>
      <span v-if="!collapsed">Inspector</span>
      <IconButton v-else label="Expand inspector" @click="emit('toggle')">‹</IconButton>
    </header>

    <div v-if="!collapsed" class="inspector__body">
      <div class="inspector__tabs" role="tablist">
        <button
          type="button"
          role="tab"
          :aria-selected="tab === 'citations'"
          :class="{ active: tab === 'citations' }"
          @click="tab = 'citations'"
        >Citations</button>
        <button
          type="button"
          role="tab"
          :aria-selected="tab === 'authors'"
          :class="{ active: tab === 'authors' }"
          @click="tab = 'authors'"
        >Authors</button>
      </div>

      <section v-if="tab === 'citations'">
        <p v-if="!report" class="hint">Citations will appear after a report is ready.</p>
        <p v-else-if="!citations.length" class="hint">No citation links in this report.</p>
        <ul v-else class="citation-list">
          <li v-for="link in citations" :key="`${link.paper_id}:${link.token}`">
            <button type="button" @click="emit('openPaper', link.paper_id)">
              <code>{{ link.token }}</code>
              <span>{{ link.paper_id }}</span>
            </button>
          </li>
        </ul>
      </section>

      <section v-else>
        <p class="hint">Author relationships will appear here.</p>
        <p class="hint hint--small">This panel is reserved for the citation and author graph.</p>
      </section>
    </div>
  </aside>
</template>

<style scoped>
.inspector {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-left: 1px solid var(--border);
  background: var(--surface);
}

.inspector--collapsed {
  align-items: center;
}

.inspector__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 48px;
  padding: 0 var(--space-2);
  border-bottom: 1px solid var(--border);
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.inspector__body {
  min-height: 0;
  overflow: auto;
  padding: var(--space-3);
}

.inspector__tabs {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
  border-bottom: 1px solid var(--border);
}

.inspector__tabs button {
  padding: 7px 0;
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 600;
}

.inspector__tabs button.active {
  border-bottom-color: var(--accent);
  color: var(--text);
}

.hint {
  color: var(--text-faint);
  font-size: 12px;
  line-height: 1.55;
}

.hint--small {
  margin-top: 6px;
  font-size: 11px;
}

.citation-list {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.citation-list button {
  display: flex;
  align-items: center;
  gap: 7px;
  width: 100%;
  padding: 7px 8px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-muted);
  font-size: 11px;
  text-align: left;
}

.citation-list button:hover {
  background: var(--surface-muted);
  color: var(--text);
}

.citation-list code {
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 10px;
}
</style>
