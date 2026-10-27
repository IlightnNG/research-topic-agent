<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { api } from "@/api/endpoints";
import type { PaperDetail, Report } from "@/api/types";

const props = defineProps<{ paperId: string; report: Report | null }>();

const paper = ref<PaperDetail | null>(null);
const error = ref("");
const loading = ref(false);

const citations = computed(() => {
  const claims = props.report?.claims ?? [];
  return claims.filter((claim) =>
    (claim.citations ?? []).some((citation) => citation.paper_id === props.paperId),
  );
});

watch(
  () => props.paperId,
  async (id) => {
    loading.value = true;
    error.value = "";
    try {
      paper.value = await api.getPaper(id);
    } catch (exc) {
      error.value = exc instanceof Error ? exc.message : String(exc);
      paper.value = null;
    } finally {
      loading.value = false;
    }
  },
  { immediate: true },
);
</script>

<template>
  <div class="stack paper-pane">
    <el-alert v-if="error" type="error" :title="error" :closable="false" show-icon />
    <template v-if="paper">
      <div class="stack" style="gap: var(--space-1)">
        <h3 class="title-md">{{ paper.title }}</h3>
        <p class="muted">
          {{ paper.paper_id }} · {{ paper.source || "unknown venue" }}
          <template v-if="paper.year"> · {{ paper.year }}</template>
          <template v-if="paper.authors.length"> · {{ paper.authors.join(", ") }}</template>
        </p>
      </div>
      <p class="paper-abstract">{{ paper.abstract || "No abstract available." }}</p>
      <div class="cluster">
        <el-tag v-if="paper.pdf_available" size="small" type="success">PDF available</el-tag>
        <el-tag v-else size="small" type="info">abstract only</el-tag>
        <a v-if="paper.pdf_url" :href="paper.pdf_url" target="_blank" rel="noreferrer">Download PDF</a>
      </div>

      <h4 class="title-md">Claims in this report</h4>
      <el-empty v-if="!citations.length" description="No report claim cites this paper yet." />
      <article v-for="claim in citations" :key="claim.text" class="claim-card">
        <p>{{ claim.text }}</p>
        <p v-if="claim.citations?.[0]?.snippet" class="muted mono">
          “{{ claim.citations[0].snippet }}”
        </p>
      </article>
    </template>
    <p v-else-if="loading" class="muted">Loading paper…</p>
  </div>
</template>

<style scoped>
.paper-pane {
  gap: var(--space-3);
  max-width: 860px;
}
.paper-abstract {
  white-space: pre-wrap;
  line-height: 1.7;
}
.claim-card {
  padding: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface-soft);
}
</style>
