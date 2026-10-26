<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import EmptyState from "@/components/EmptyState.vue";
import ErrorBanner from "@/components/ErrorBanner.vue";
import SectionCard from "@/components/SectionCard.vue";
import TopicShell from "@/components/TopicShell.vue";
import { useChatStore } from "@/stores/chat";
import { useTopicsStore } from "@/stores/topics";

const route = useRoute();
const topics = useTopicsStore();
const chat = useChatStore();
const topicId = String(route.params.topicId ?? "");
const input = ref("");

onMounted(async () => {
  await topics.loadOne(topicId);
  await topics.load();
  await chat.load(topicId);
});

function send(): void {
  const text = input.value;
  if (!text.trim() || chat.loading) return;
  input.value = "";
  void chat.send(topicId, text);
}
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
        <el-button size="small" type="primary" text @click="chat.startNew(topicId)">
          + 新建对话
        </el-button>
      </div>
      <ul v-if="chat.sessions.length" class="chat-sessions">
        <li
          v-for="item in chat.sessions"
          :key="item.id"
          :class="{ current: item.id === chat.session?.id }"
        >
          {{ new Date(item.created_at || Date.now()).toLocaleString() }}
        </li>
      </ul>
      <EmptyState v-else compact title="暂无对话" hint="在右侧提第一个问题，会自动创建会话。" />
    </template>

    <SectionCard title="Chat" subtitle="回答必须带引用；没有命中证据会明确拒答。">
      <ErrorBanner v-if="chat.error" :message="chat.error" @retry="chat.load(topicId)" />

      <div class="chat-log">
        <div v-for="message in chat.messages" :key="message.id" class="chat-msg" :class="message.role">
          <p>{{ message.content }}</p>
          <div v-if="message.citations.length" class="cluster">
            <el-tag v-for="citation in message.citations" :key="citation.paper_id" size="small" type="info">
              {{ citation.paper_id }}
            </el-tag>
          </div>
          <details v-if="message.trace.length">
            <summary class="muted">工具轨迹</summary>
            <ul class="trace">
              <li v-for="(step, index) in message.trace" :key="index">
                {{ step.tool }} · {{ step.ok ? "ok" : "fail" }}
              </li>
            </ul>
          </details>
        </div>
        <p v-if="!chat.messages.length" class="muted">
          问一个关于本 topic 的问题，例如「工具使用对 agent 有什么影响？」
        </p>
      </div>

      <div class="cluster chat-input">
        <el-input v-model="input" placeholder="输入问题，回车发送" @keyup.enter="send" />
        <el-button type="primary" :loading="chat.loading" @click="send">发送</el-button>
        <el-button v-if="chat.loading" @click="chat.abort">中止</el-button>
      </div>
    </SectionCard>
  </TopicShell>
</template>

<style scoped>
.side-head {
  padding: var(--space-3);
}
.chat-sessions {
  list-style: none;
  margin: 0;
  padding: 0;
}
.chat-sessions li {
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border);
  font-size: 13px;
  color: var(--muted);
}
.chat-sessions li.current {
  color: var(--text);
  background: var(--surface-2);
}
.chat-log {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  max-height: 52vh;
  overflow-y: auto;
  padding: var(--space-2) 0;
}
.chat-msg {
  max-width: 78%;
  padding: var(--space-3);
  border-radius: var(--radius-2);
  background: var(--surface-2);
}
.chat-msg.user {
  align-self: flex-end;
  background: var(--accent-soft);
}
.chat-msg p {
  margin: 0 0 var(--space-2);
  white-space: pre-wrap;
}
.chat-msg details {
  margin-top: var(--space-2);
}
.trace {
  margin: var(--space-1) 0 0;
  padding-left: var(--space-4);
  font-size: 12px;
  color: var(--muted);
}
.chat-input {
  margin-top: var(--space-3);
  align-items: center;
}
</style>
