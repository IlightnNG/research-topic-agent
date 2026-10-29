<script setup lang="ts">
import { ref, watch } from "vue";

import { api } from "@/api/endpoints";
import type { AuthorDetail } from "@/api/types";

const props = defineProps<{ authorId: string }>();
const emit = defineEmits<{ close: []; "open-paper": [string] }>();

const author = ref<AuthorDetail | null>(null);
const error = ref("");
const loading = ref(false);

watch(
  () => props.authorId,
  async (id) => {
    loading.value = true;
    error.value = "";
    try {
      author.value = await api.getAuthor(id);
    } catch (exc) {
      error.value = exc instanceof Error ? exc.message : String(exc);
      author.value = null;
    } finally {
      loading.value = false;
    }
  },
  { immediate: true },
);
</script>

<template>
  <aside class="author-pane">
    <div class="between">
      <h4 class="title-md">Author</h4>
      <el-button size="small" text @click="emit('close')">Close</el-button>
    </div>

    <el-alert v-if="error" type="error" :title="error" :closable="false" show-icon />
    <p v-else-if="loading" class="muted">Loading…</p>
    <template v-else-if="author">
      <div class="stack" style="gap: var(--space-1)">
        <strong>{{ author.name }}</strong>
        <p class="muted">
          {{ author.institution || "unknown institution" }}
          <template v-if="author.orcid"> · {{ author.orcid }}</template>
        </p>
        <p class="muted">{{ author.works_count }} indexed works</p>
      </div>

      <h5 class="title-sm">Recent papers</h5>
      <el-empty v-if="!author.papers.length" description="No papers indexed." />
      <ul class="author-list">
        <li v-for="paper in author.papers" :key="paper.paper_id">
          <button type="button" class="link-button" @click="emit('open-paper', paper.paper_id)">
            {{ paper.title }}
          </button>
          <span class="muted"> · {{ paper.year || "n.d." }} · {{ paper.source || "unknown" }}</span>
        </li>
      </ul>

      <template v-if="author.coauthors.length">
        <h5 class="title-sm">Co-authors</h5>
        <ul class="author-list">
          <li v-for="person in author.coauthors" :key="person.author_id">
            {{ person.name }} <span class="muted">({{ person.shared_papers }})</span>
          </li>
        </ul>
      </template>
    </template>
  </aside>
</template>

<style scoped>
.author-pane {
  width: 320px;
  flex: 0 0 320px;
  padding: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface-soft);
  position: sticky;
  top: var(--space-3);
}
.author-list {
  margin: 0;
  padding-left: var(--space-4);
  line-height: 1.6;
}
.link-button {
  border: 0;
  background: none;
  padding: 0;
  color: var(--color-accent, #2563eb);
  cursor: pointer;
  text-align: left;
}
.title-sm {
  margin: var(--space-3) 0 var(--space-1);
}
</style>
