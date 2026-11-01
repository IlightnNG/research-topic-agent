<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import type { TopicBrief } from '@/types'

defineProps<{
  direction: string
  brief?: TopicBrief
}>()

const open = ref(false)
const root = ref<HTMLElement | null>(null)

function onDocumentClick(event: MouseEvent): void {
  if (root.value && !root.value.contains(event.target as Node)) open.value = false
}

onMounted(() => document.addEventListener('click', onDocumentClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocumentClick))
</script>

<template>
  <div ref="root" class="scope">
    <button type="button" class="scope__trigger" @click="open = !open">
      <span class="scope__dot" aria-hidden="true"></span>
      {{ direction }}
      <span class="scope__caret" aria-hidden="true">⌄</span>
    </button>
    <div v-if="open" class="scope__popover" role="dialog" aria-label="Research scope">
      <h3>Research scope</h3>
      <p class="scope__statement">{{ brief?.scope_statement || `Stay within ${direction}.` }}</p>
      <div v-if="brief" class="scope__grid">
        <section>
          <h4>Include</h4>
          <ul>
            <li v-for="item in brief.include_criteria" :key="item">{{ item }}</li>
          </ul>
        </section>
        <section>
          <h4>Exclude</h4>
          <ul v-if="brief.exclude_criteria.length">
            <li v-for="item in brief.exclude_criteria" :key="item">{{ item }}</li>
          </ul>
          <p v-else class="muted">No exclusions.</p>
        </section>
      </div>
      <div v-if="brief?.search_queries?.length" class="scope__queries">
        <h4>Search queries</h4>
        <code v-for="query in brief.search_queries" :key="query">{{ query }}</code>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scope {
  position: relative;
}

.scope__trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 28px;
  padding: 0 9px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface);
  color: var(--text-muted);
  font-size: 12px;
}

.scope__trigger:hover {
  border-color: var(--border-strong);
  color: var(--text);
}

.scope__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
}

.scope__caret {
  color: var(--text-faint);
}

.scope__popover {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  z-index: 40;
  width: 380px;
  max-width: min(380px, 80vw);
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
  box-shadow: 0 12px 30px rgb(0 0 0 / 10%);
}

.scope__popover h3 {
  margin-bottom: 8px;
  font-size: 13px;
}

.scope__popover h4 {
  margin-bottom: 4px;
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.scope__statement {
  margin-bottom: 12px;
  color: var(--text-muted);
  font-size: 13px;
}

.scope__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.scope__grid ul {
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.6;
}

.scope__grid li::before {
  content: '· ';
  color: var(--text-faint);
}

.scope__queries {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.scope__queries code {
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 11px;
}
</style>
