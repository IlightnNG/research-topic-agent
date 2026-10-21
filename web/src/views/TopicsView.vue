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
    dialogError.value = "id 只能是小写字母/数字/短横线，2–41 字符";
    return;
  }
  if (form.value.scope.trim().length < 10) {
    dialogError.value = "scope 至少写 10 个字（写清研究什么、不研究什么）";
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
    <PageHeader title="Topics" subtitle="一个 topic 是一个研究纲领；报告与对话都在它下面。">
      <template #actions>
        <el-button type="primary" @click="openDialog">新建 topic</el-button>
      </template>
    </PageHeader>

    <ErrorBanner v-if="store.error" :message="store.error" @retry="store.load" />
    <el-skeleton v-if="store.loading" :rows="4" animated />

    <el-collapse v-if="!store.loading && archived.length" class="archived">
      <el-collapse-item :title="`已归档（${archived.length}）`" name="archived">
        <div class="topic-grid">
          <article v-for="topic in archived" :key="topic.id" class="topic-card stack">
            <div class="between">
              <strong class="mono">{{ topic.id }}</strong>
              <el-button size="small" text @click="archive(topic)">恢复</el-button>
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
                    {{ topic.status === "archived" ? "恢复" : "归档" }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
        <h3 class="title-md clickable" @click="openReport(topic.id)">{{ topic.name }}</h3>
        <p class="muted line-clamp-2">{{ topic.scope_statement }}</p>
        <p class="muted mono">
          {{ store.counts[topic.id]?.reports ?? 0 }} 份报告 · {{ store.counts[topic.id]?.runs ?? 0 }} 次运行
        </p>
        <div class="cluster">
          <el-button type="primary" size="small" @click="openReport(topic.id)">Report</el-button>
          <el-button size="small" @click="openChat(topic.id)">Chat</el-button>
        </div>
      </article>
    </div>

    <EmptyState
      v-if="!store.loading && !store.items.length"
      title="还没有 topic"
      hint="先建一个研究纲领，然后在 Report 页生成第一份周报。"
    >
      <el-button type="primary" @click="openDialog">新建 topic</el-button>
    </EmptyState>

    <DialogForm
      v-model="dialogOpen"
      title="新建 topic"
      confirm-text="创建"
      :busy="busy"
      :error-text="dialogError"
      @confirm="submit"
    >
      <el-input v-model="form.id" placeholder="id（slug，如 ai-agents）" />
      <el-input v-model="form.name" placeholder="名称" />
      <el-input
        v-model="form.scope"
        type="textarea"
        :rows="3"
        placeholder="scope：研究什么、不研究什么"
      />
      <el-input v-model="form.keywords" placeholder="keywords（逗号分隔，可选）" />
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="不配置数据源时，运行会跳过抓取（报告会标注 degraded）"
      />
    </DialogForm>
  </div>
</template>

