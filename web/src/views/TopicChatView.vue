<script setup lang="ts">
import { onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";

import EmptyState from "@/components/EmptyState.vue";
import PageHeader from "@/components/PageHeader.vue";

const route = useRoute();
const router = useRouter();
const topicId = String(route.params.topicId ?? "");

onMounted(() => undefined);
</script>

<template>
  <div class="stack" style="padding: var(--space-5)">
    <PageHeader
      title="Chat"
      subtitle="对话功能将在 Phase 3 开放：问题 → 证据检索 → 带引用的回答。"
      back-to="/topics"
      back-label="Topics"
    />
    <EmptyState
      title="对话功能尚未开放"
      hint="后端返回 501 E_FEATURE_DISABLED。Phase 3 会复用报告的引用体系，回答同样可溯源。"
    >
      <el-button
        type="primary"
        @click="router.push({ name: 'topic-reports', params: { topicId } })"
      >
        去 Report 页
      </el-button>
    </EmptyState>
  </div>
</template>
