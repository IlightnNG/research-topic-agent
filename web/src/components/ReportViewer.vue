<script setup lang="ts">
import { ElMessage } from "element-plus";
import { computed, nextTick, ref } from "vue";

import type { Report } from "@/api/types";

import ClaimTable from "./ClaimTable.vue";
import PaperIndexTable from "./PaperIndexTable.vue";
import TocNav from "./TocNav.vue";

const props = defineProps<{ report: Report }>();
const emit = defineEmits<{ why: [number]; "open-paper": [string] }>();

const activeSection = ref<string | null>(null);
const sha = computed(() => props.report.content_sha?.slice(0, 8) ?? "");

// 后端目前把 sections 由 claims 派生（一 claim 一节），会与下方 Claims 表重复。
// 这里只在"分节确有独立内容"时渲染分节与目录，避免重复。
const showSections = computed(() => {
  const sections = props.report.sections ?? [];
  if (!sections.length) return false;
  const claims = props.report.claims ?? [];
  const isEcho =
    sections.length === claims.length &&
    sections.every((section, index) => section.title.startsWith("Evidence ") && section.body === claims[index]?.text);
  return !isEcho;
});

type Part = { text: string; claim: number | null };

function parts(body: string): Part[] {
  const result: Part[] = [];
  const pattern = /\[C(\d+)\]/g;
  let last = 0;
  for (const match of body.matchAll(pattern)) {
    const index = match.index ?? 0;
    if (index > last) result.push({ text: body.slice(last, index), claim: null });
    result.push({ text: match[0], claim: Number(match[1]) });
    last = index + match[0].length;
  }
  if (last < body.length) result.push({ text: body.slice(last), claim: null });
  return result;
}

function openClaim(index: number): void {
  const claim = props.report.claims?.[index - 1];
  const paperId = claim?.citations?.[0]?.paper_id;
  if (paperId) emit("open-paper", paperId);
}

async function jump(sectionId: string): Promise<void> {
  activeSection.value = sectionId;
  await nextTick();
  document.getElementById(`section-${sectionId}`)?.scrollIntoView({ behavior: "smooth" });
}

async function copyMarkdown(): Promise<void> {
  await navigator.clipboard.writeText(props.report.content_md);
  ElMessage.success("Markdown copied");
}
</script>

<template>
  <div class="stack">
    <el-alert
      v-if="report.degraded"
      type="warning"
      show-icon
      :closable="false"
      title="No citable evidence; the report is degraded"
    />
    <div class="between">
      <div class="stack" style="gap: var(--space-1)">
        <h3 class="title-md">{{ report.title }}</h3>
        <p class="muted mono">
          sha {{ sha }} · run {{ report.run_id }} · {{ report.n_claims }} claims
        </p>
      </div>
      <el-button size="small" @click="copyMarkdown">Copy Markdown</el-button>
    </div>

    <div class="report-body">
      <article class="grow">
        <section
          v-for="section in showSections ? report.sections : []"
          :id="`section-${section.id}`"
          :key="section.id"
          class="stack report-section"
        >
          <h4 class="title-md">{{ section.title }}</h4>
          <PaperIndexTable
            v-if="section.kind === 'paper_index'"
            :section="section"
            @open-paper="(paperId) => emit('open-paper', paperId)"
          />
          <p v-else class="section-text">
            <template v-for="(part, index) in parts(section.body)" :key="index">
              <button
                v-if="part.claim"
                type="button"
                class="cite-chip"
                :aria-label="`Open paper for claim ${part.claim}`"
                @click="openClaim(part.claim)"
              >
                {{ part.text }}
              </button>
              <template v-else>{{ part.text }}</template>
            </template>
          </p>
        </section>

        <template v-if="!showSections">
          <h4 class="title-md">Claims</h4>
          <ClaimTable :claims="report.claims" @why="(index) => emit('why', index)" />
        </template>

        <details style="margin-top: var(--space-4)">
          <summary class="muted">Raw Markdown</summary>
          <pre class="raw mono">{{ report.content_md }}</pre>
        </details>
      </article>
      <TocNav v-if="showSections" :sections="report.sections" @jump="jump" />
    </div>
  </div>
</template>

<style scoped>
.report-body {
  display: flex;
  gap: var(--space-5);
  align-items: flex-start;
}
.report-section {
  padding-bottom: var(--space-3);
  border-bottom: 1px dashed var(--color-border);
}
.section-text {
  white-space: pre-wrap;
  line-height: 1.75;
}
.cite-chip {
  border: 1px solid var(--color-border);
  background: var(--color-surface-soft);
  color: var(--color-accent, #2563eb);
  border-radius: 4px;
  padding: 0 0.25rem;
  font: inherit;
  cursor: pointer;
}
.cite-chip:hover {
  background: var(--color-accent-soft, #dbeafe);
}
.raw {
  white-space: pre-wrap;
  background: var(--color-surface-soft);
  padding: var(--space-3);
  border-radius: var(--radius-sm);
}
</style>
