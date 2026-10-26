<script setup lang="ts">
import { ElMessage } from "element-plus";
import { computed, nextTick, ref } from "vue";

import type { Report } from "@/api/types";

import ClaimTable from "./ClaimTable.vue";
import TocNav from "./TocNav.vue";

const props = defineProps<{ report: Report }>();
const emit = defineEmits<{ why: [number] }>();

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
          <p>{{ section.body }}</p>
        </section>

        <h4 class="title-md">Claims</h4>
        <ClaimTable :claims="report.claims" @why="(index) => emit('why', index)" />

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
.raw {
  white-space: pre-wrap;
  background: var(--color-surface-soft);
  padding: var(--space-3);
  border-radius: var(--radius-sm);
}
</style>
