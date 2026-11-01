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
