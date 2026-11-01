<script setup lang="ts">
import type { Paper } from '@/types'

defineProps<{
  paper: Paper
}>()
</script>

<template>
  <article class="paper-meta">
    <p class="paper-meta__eyebrow">Paper</p>
    <h1>{{ paper.title }}</h1>
    <p class="paper-meta__byline">
      {{ paper.authors.join(', ') }}
      <span v-if="paper.year"> · {{ paper.year }}</span>
      <span v-if="paper.venue"> · {{ paper.venue }}</span>
    </p>
    <section>
      <h2>Abstract</h2>
      <p>{{ paper.abstract }}</p>
    </section>
    <p v-if="paper.source_url" class="paper-meta__links">
      <a :href="paper.source_url" target="_blank" rel="noreferrer">Open source</a>
    </p>
  </article>
</template>

<style scoped>
.paper-meta {
  max-width: 780px;
  margin: 0 auto;
  padding: 32px 28px 80px;
}

.paper-meta__eyebrow {
  margin-bottom: 5px;
  color: var(--text-faint);
  font-size: 10px;
  font-weight: 650;
  letter-spacing: 0.07em;
  text-transform: uppercase;
}

.paper-meta h1 {
  font-size: 24px;
  font-weight: 680;
  line-height: 1.25;
}

.paper-meta__byline {
  margin-top: 8px;
  color: var(--text-muted);
  font-size: 12px;
}

.paper-meta section {
  margin-top: 28px;
  padding-top: 18px;
  border-top: 1px solid var(--border);
}

.paper-meta h2 {
  margin-bottom: 8px;
  font-size: 15px;
  font-weight: 650;
}

.paper-meta section p {
  color: var(--text);
  font-size: 14px;
  line-height: 1.7;
}

.paper-meta__links {
  margin-top: 20px;
  font-size: 12px;
}
</style>
