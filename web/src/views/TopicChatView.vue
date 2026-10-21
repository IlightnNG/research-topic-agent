<script setup lang="ts">
import { onMounted } from "vue";
import { useRoute } from "vue-router";

import EmptyState from "@/components/EmptyState.vue";
import SectionCard from "@/components/SectionCard.vue";
import TopicShell from "@/components/TopicShell.vue";
import { useTopicsStore } from "@/stores/topics";

const route = useRoute();
const topics = useTopicsStore();
const topicId = String(route.params.topicId ?? "");

onMounted(async () => {
  await topics.loadOne(topicId);
  await topics.load();
});
</script>

<template>
  <TopicShell
    :topic-id="topicId"
    :title="topics.current?.name ?? topicId"
    :subtitle="topics.current?.scope_statement ?? ''"
    active="chat"
  >
    <template #side>
      <div class="between side-head">
        <strong>Conversations</strong>
        <el-button size="small" type="primary" text disabled>+ 新建对话</el-button>
      </div>
      <EmptyState
        compact
        title="暂无对话"
        hint="Phase 3 开放后，这里按时间列出该 topic 的会话。"
      />
    </template>

    <SectionCard
      title="对话功能尚未开放"
      subtitle="后端返回 501 E_FEATURE_DISABLED。Phase 3 会复用报告的引用体系，回答同样可溯源。"
    >
      <p class="muted">
        计划形态：左侧会话列表、右侧对话流；每条回答可展开引用（paper_id + 片段），与周报共用同一套证据。
      </p>
    </SectionCard>
  </TopicShell>
</template>

<style scoped>
.side-head {
  padding: var(--space-3);
}
</style>
