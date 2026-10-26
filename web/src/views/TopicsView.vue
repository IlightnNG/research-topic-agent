<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { describeError } from "@/api/client";
import DialogForm from "@/components/DialogForm.vue";
import EmptyState from "@/components/EmptyState.vue";
import ErrorBanner from "@/components/ErrorBanner.vue";
import PageHeader from "@/components/PageHeader.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { useTopicsStore } from "@/stores/topics";
import type { Topic } from "@/api/types";

const router = useRouter();
const store = useTopicsStore();

const dialogOpen = ref(false);
const busy = ref(false);
const dialogError = ref("");
const form = ref({ id: "", name: "", scope: "", keywords: "" });

function openDialog(): void {
  form.value = { id: "", name: "", scope: "", keywords: "" };
  dialogError.value = "";
  dialogOpen.value = true;
}

async function submit(): Promise<void> {
  dialogError.value = "";
  if (!/^[a-z0-9][a-z0-9-]{1,40}$/.test(form.value.id)) {
    dialogError.value = "id must be lowercase letters/digits/hyphens, 2-41 chars";
    return;
  }
  if (form.value.scope.trim().length < 10) {
    dialogError.value = "scope needs at least 10 characters (in/out of scope)";
    return;
  }
  busy.value = true;
  try {
    await store.create({
      id: form.value.id.trim(),
      name: form.value.name.trim() || form.value.id.trim(),
      scope_statement: form.value.scope.trim(),
      scope_keywords: form.value.keywords
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    });
    dialogOpen.value = false;
  } catch (err) {
    dialogError.value = describeError(err);
  } finally {
    busy.value = false;
  }
}

async function archive(topic: Topic): Promise<void> {
  await store.patch(topic.id, { status: topic.status === "archived" ? "active" : "archived" });
}

function openReport(topicId: string): void {
  void router.push({ name: "topic-reports", params: { topicId } });
}

function openChat(topicId: string): void {
  void router.push({ name: "topic-chat", params: { topicId } });
}

const active = computed(() => store.items.filter((topic) => topic.status !== "archived"));
const archived = computed(() => store.items.filter((topic) => topic.status === "archived"));

onMounted(store.load);
</script>

<template>
  <div class="stack" style="padding: var(--space-5)">
    <PageHeader title="Topics" subtitle="A topic is a research program; reports and chat live under it.">
      <template #actions>
        <el-button type="primary" @click="openDialog">New topic</el-button>
      </template>
    </PageHeader>

    <ErrorBanner v-if="store.error" :message="store.error" @retry="store.load" />
    <el-skeleton v-if="store.loading" :rows="4" animated />

    <el-collapse v-if="!store.loading && archived.length" class="archived">
      <el-collapse-item :title="`Archived (${archived.length})`" name="archived">
        <div class="topic-grid">
          <article v-for="topic in archived" :key="topic.id" class="topic-card stack">
            <div class="between">
              <strong class="mono">{{ topic.id }}</strong>
              <el-button size="small" text @click="archive(topic)">Restore</el-button>
            </div>
            <p class="muted line-clamp-2">{{ topic.scope_statement }}</p>
          </article>
        </div>
      </el-collapse-item>
    </el-collapse>

    <div v-else class="topic-grid">
      <article v-for="topic in active" :key="topic.id" class="topic-card stack">
        <div class="between">
          <strong class="mono">{{ topic.id }}</strong>
          <div class="cluster">
            <StatusBadge :state="topic.status ?? 'active'" />
            <el-dropdown trigger="click">
              <el-button size="small" text>⋯</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="archive(topic)">
                    {{ topic.status === "archived" ? "Restore" : "Archive" }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
        <h3 class="title-md clickable" @click="openReport(topic.id)">{{ topic.name }}</h3>
        <p class="muted line-clamp-2">{{ topic.scope_statement }}</p>
        <p class="muted mono">
          {{ store.counts[topic.id]?.reports ?? 0 }} reports · {{ store.counts[topic.id]?.runs ?? 0 }} runs
        </p>
        <div class="cluster">
          <el-button type="primary" size="small" @click="openReport(topic.id)">Report</el-button>
          <el-button size="small" @click="openChat(topic.id)">Chat</el-button>
        </div>
      </article>
    </div>

    <EmptyState
      v-if="!store.loading && !store.items.length"
      title="No topics yet"
      hint="Create a research program, then generate your first report."
    >
      <el-button type="primary" @click="openDialog">New topic</el-button>
    </EmptyState>

    <DialogForm
      v-model="dialogOpen"
      title="New topic"
      confirm-text="Create"
      :busy="busy"
      :error-text="dialogError"
      @confirm="submit"
    >
      <el-input v-model="form.id" placeholder="id (slug, e.g. ai-agents)" />
      <el-input v-model="form.name" placeholder="Name" />
      <el-input
        v-model="form.scope"
        type="textarea"
        :rows="3"
        placeholder="scope: what is in / out"
      />
      <el-input v-model="form.keywords" placeholder="keywords (comma separated, optional)" />
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="Without a data source, runs skip fetching (report marked degraded)"
      />
    </DialogForm>
  </div>
</template>

