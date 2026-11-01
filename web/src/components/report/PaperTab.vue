<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { api } from '@/api/client'
import type { Paper } from '@/types'
import EmptyState from '@/components/ui/EmptyState.vue'
import PaperMetadata from './PaperMetadata.vue'

const props = defineProps<{
  paperId: string
}>()

const paper = ref<Paper>()
const loading = ref(true)
const error = ref('')
const pdfFailed = ref(false)

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  pdfFailed.value = false
  try {
    paper.value = await api.getPaper(props.paperId)
    if (!paper.value) error.value = 'Paper not found.'
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Could not load paper.'
  } finally {
    loading.value = false
  }
}

function onPdfError(): void {
  pdfFailed.value = true
}

onMounted(load)
watch(() => props.paperId, load)
</script>

<template>
  <section class="paper">
    <p v-if="loading" class="state">Loading paper…</p>
    <EmptyState v-else-if="error" title="Paper unavailable" :description="error" />
    <template v-else-if="paper">
      <div v-if="paper.pdf_url && !pdfFailed" class="pdf">
        <header class="pdf__bar">
          <span>{{ paper.title }}</span>
          <a :href="paper.pdf_url" target="_blank" rel="noreferrer">Open PDF</a>
        </header>
        <iframe
          :src="paper.pdf_url"
          :title="paper.title"
          class="pdf__frame"
          @error="onPdfError"
        ></iframe>
      </div>
      <PaperMetadata v-else :paper="paper" />
      <p v-if="pdfFailed" class="fallback">PDF could not be displayed. Showing metadata instead.</p>
    </template>
  </section>
</template>

<style scoped>
.paper {
  min-height: 100%;
  background: var(--surface);
}

.state {
  padding: 32px;
  color: var(--text-muted);
  font-size: 13px;
}

.pdf {
  display: flex;
  flex-direction: column;
  height: calc(100vh - var(--topbar-h) - var(--tab-h) - 1px);
}

.pdf__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  min-height: 38px;
  padding: 0 16px;
  border-bottom: 1px solid var(--border);
  color: var(--text-muted);
  font-size: 12px;
}

.pdf__frame {
  flex: 1;
  width: 100%;
  border: 0;
}

.fallback {
  padding: 12px 28px;
  color: var(--warning);
  font-size: 12px;
}
</style>
