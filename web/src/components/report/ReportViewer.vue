<script setup lang="ts">
import type { Report } from '@/types'
import ReportBody from './ReportBody.vue'

defineProps<{
  report: Report
}>()

const emit = defineEmits<{
  openPaper: [paperId: string]
}>()
</script>

<template>
  <article class="report">
    <header class="report__head">
      <p class="report__eyebrow">Report</p>
      <h1>{{ report.title }}</h1>
      <p class="report__meta">{{ report.state }} · {{ report.word_count.toLocaleString() }} words</p>
      <div v-if="report.quality" class="quality" :class="{ 'quality--bad': !report.quality.accepted }">
        <span class="quality__badge">
          {{ report.quality.accepted ? 'Quality gate passed' : 'Quality needs review' }}
        </span>
        <span v-if="report.quality.metrics" class="quality__metrics">
          {{ report.quality.metrics.papers ?? 0 }} papers ·
          {{ report.quality.metrics.fulltext ?? 0 }} fulltext ·
          {{ report.quality.metrics.claims ?? 0 }} claims ·
          {{ report.quality.metrics.sections ?? 0 }} sections ·
          citation {{ report.quality.metrics.citation_coverage ?? 0 }}
        </span>
        <span v-if="report.quality.audit" class="quality__audit">
          audit: {{ report.quality.audit.status }}
        </span>
      </div>
    </header>

    <div class="report__body">
      <section v-for="section in report.sections" :key="section.section_id" class="section">
        <h2 v-if="section.title !== report.title">{{ section.title }}</h2>
        <ReportBody
          :text="section.body"
          :links="section.paper_links"
          @open-paper="emit('openPaper', $event)"
        />
      </section>
    </div>
  </article>
</template>

<style scoped>
.report {
  max-width: 820px;
  margin: 0 auto;
  padding: 32px 28px 80px;
}

.report__eyebrow {
  margin-bottom: 5px;
  color: var(--text-faint);
  font-size: 10px;
  font-weight: 650;
  letter-spacing: 0.07em;
  text-transform: uppercase;
}

.report h1 {
  font-size: 26px;
  font-weight: 680;
  letter-spacing: -0.015em;
  line-height: 1.2;
}

.report__meta {
  margin-top: 8px;
  color: var(--text-muted);
  font-size: 12px;
}

.quality {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface-raised);
  color: var(--text-muted);
  font-size: 10px;
}

.quality--bad {
  border-color: var(--warning);
}

.quality__badge {
  color: var(--success);
  font-weight: 650;
}

.quality--bad .quality__badge {
  color: var(--warning);
}

.quality__metrics,
.quality__audit {
  font-family: var(--font-mono);
}

.report__body {
  margin-top: 28px;
}

.section {
  padding: 20px 0;
  border-top: 1px solid var(--border);
}

.section h2 {
  margin-bottom: 10px;
  font-size: 17px;
  font-weight: 650;
}

</style>
