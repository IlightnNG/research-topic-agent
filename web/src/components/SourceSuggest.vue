<script setup lang="ts">
import { computed, ref } from "vue";

import { api } from "@/api/endpoints";
import type { SourceConfig, SourcePreview, SourceSuggestion } from "@/api/types";

const props = defineProps<{ scope: string }>();
const emit = defineEmits<{ "update:sources": [SourceConfig | null] }>();

const suggestion = ref<SourceSuggestion | null>(null);
const selected = ref<string[]>([]);
const manualId = ref("");
const year = ref<number | null>(null);
const busy = ref(false);
const error = ref("");
const preview = ref<SourcePreview | null>(null);

const resolvedVenues = computed(() =>
  (suggestion.value?.venues ?? []).filter((venue) => Boolean(venue.source_id)),
);

function selector(): SourceConfig["selector"] | null {
  const queries = suggestion.value?.queries ?? [];
  if (!selected.value.length && !queries.length) return null;
  return { venue_ids: [...selected.value], queries: [...queries], from_year: year.value };
}

function publish(): void {
  const config = selector();
  emit("update:sources", config ? { source: "openalex", selector: config } : null);
}

async function suggest(): Promise<void> {
  busy.value = true;
  error.value = "";
  preview.value = null;
  try {
    suggestion.value = await api.suggestSources(props.scope);
    year.value = suggestion.value.from_year ?? null;
    selected.value = resolvedVenues.value
      .filter((venue) => venue.confidence >= 0.9)
      .map((venue) => venue.source_id as string);
    publish();
  } catch (exc) {
    error.value = exc instanceof Error ? exc.message : String(exc);
  } finally {
    busy.value = false;
  }
}

function toggle(sourceId: string): void {
  selected.value = selected.value.includes(sourceId)
    ? selected.value.filter((item) => item !== sourceId)
    : [...selected.value, sourceId];
  publish();
}

function addManual(): void {
  const id = manualId.value.trim();
  if (!id) return;
  if (!selected.value.includes(id)) selected.value = [...selected.value, id];
  manualId.value = "";
  publish();
}

async function runPreview(): Promise<void> {
  const config = selector();
  if (!config) return;
  busy.value = true;
  error.value = "";
  try {
    preview.value = await api.previewSources({ ...config }, 5);
  } catch (exc) {
    error.value = exc instanceof Error ? exc.message : String(exc);
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <section class="stack source-suggest">
    <div class="between">
      <strong>Research sources</strong>
      <el-button size="small" :loading="busy" @click="suggest">Suggest with AI</el-button>
    </div>
    <p class="muted">
      Optional. AI proposes venue names; OpenAlex resolves them. Review before creating the topic.
    </p>

    <el-alert v-if="error" type="error" :title="error" :closable="false" show-icon />

    <template v-if="suggestion">
      <div v-if="resolvedVenues.length" class="stack">
        <label v-for="venue in resolvedVenues" :key="venue.source_id ?? ''" class="venue-row">
          <el-checkbox
            :model-value="selected.includes(venue.source_id as string)"
            @change="toggle(venue.source_id as string)"
          />
          <span>{{ venue.name }}</span>
          <span class="muted mono">{{ venue.source_id }}</span>
          <el-tag size="small" type="success">{{ Math.round(venue.confidence * 100) }}%</el-tag>
        </label>
      </div>
      <p v-else class="muted">No venue resolved; using queries only.</p>

      <p v-if="suggestion.queries.length" class="muted">
        Queries: {{ suggestion.queries.join(" · ") }}
      </p>
      <el-input v-model="manualId" placeholder="Add OpenAlex source id (e.g. S4363608652)">
        <template #append><el-button @click="addManual">Add</el-button></template>
      </el-input>
      <el-button size="small" :loading="busy" @click="runPreview">Preview 5 papers</el-button>

      <div v-if="preview" class="stack preview">
        <p class="muted">
          Sample: {{ preview.sample_count }} papers since {{ preview.since }}
        </p>
        <ul>
          <li v-for="paper in preview.items" :key="paper.paper_id">
            {{ paper.title }} <span class="muted">({{ paper.year || "n.d." }})</span>
          </li>
        </ul>
      </div>
    </template>
  </section>
</template>

<style scoped>
.source-suggest {
  gap: var(--space-2);
  padding: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}
.venue-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.preview {
  max-height: 220px;
  overflow: auto;
  font-size: 0.9rem;
}
</style>
