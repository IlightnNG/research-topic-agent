<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import EmptyState from "@/components/EmptyState.vue";
import ErrorBanner from "@/components/ErrorBanner.vue";
import SectionCard from "@/components/SectionCard.vue";
import TopicShell from "@/components/TopicShell.vue";
import { t } from "@/i18n";
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
        <strong>{{ t("chat.conversations") }}</strong>
        <el-button size="small" type="primary" text @click="chat.startNew(topicId)">
          + {{ t("chat.new") }}
        </el-button>
      </div>
      <ul v-if="chat.sessions.length" class="chat-sessions">
        <li
          v-for="item in chat.sessions"
          :key="item.id"
          :class="{ current: item.id === chat.session?.id }"
          @click="chat.selectSession(topicId, item.id)"
        >
          <span class="session-preview">{{ item.preview || t("chat.new") }}</span>
          <small class="muted">
            {{ new Date(item.last_message_at || item.created_at || Date.now()).toLocaleString() }}
          </small>
        </li>
      </ul>
      <EmptyState v-else compact :title="t('chat.emptyTitle')" :hint="t('chat.emptyHint')" />
    </template>

    <SectionCard title="Chat" :subtitle="t('chat.subtitle')">
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
            <summary class="muted">{{ t("chat.toolTrace") }}</summary>
            <ul class="trace">
              <li v-for="(step, index) in message.trace" :key="index">
                {{ step.tool }} · {{ step.ok ? "ok" : "fail" }}
              </li>
            </ul>
          </details>
        </div>
        <p v-if="!chat.messages.length" class="muted">{{ t("chat.noMessages") }}</p>
      </div>

      <div class="cluster chat-input">
        <el-input v-model="input" :placeholder="t('chat.placeholder')" @keyup.enter="send" />
        <el-button type="primary" :loading="chat.loading" @click="send">{{ t("chat.send") }}</el-button>
        <el-button v-if="chat.loading" @click="chat.abort">{{ t("chat.stop") }}</el-button>
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
.session-preview {
  display: block;
  color: var(--text);
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
