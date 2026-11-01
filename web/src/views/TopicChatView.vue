<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTopicsStore } from '@/stores/topics'
import { useLayoutStore } from '@/stores/layout'
import { useChatStore } from '@/stores/chat'
import type { Conversation } from '@/types'
import TopicHeader from '@/components/layout/TopicHeader.vue'
import Button from '@/components/ui/Button.vue'
import IconButton from '@/components/ui/IconButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import ChatMessageItem from '@/components/chat/ChatMessageItem.vue'
import ChatComposer from '@/components/chat/ChatComposer.vue'

const route = useRoute()
const router = useRouter()
const topics = useTopicsStore()
const layout = useLayoutStore()
const chat = useChatStore()

const topicId = computed(() => String(route.params.topicId))
const topic = computed(() => topics.byId[topicId.value])
const scroller = ref<HTMLElement | null>(null)
const pendingDelete = ref<Conversation | null>(null)
const deleteBusy = ref(false)
const menuFor = ref('')
const menuRoot = ref<HTMLElement | null>(null)

function onDocumentClick(event: MouseEvent): void {
  if (menuRoot.value && !menuRoot.value.contains(event.target as Node)) menuFor.value = ''
}

onMounted(() => document.addEventListener('click', onDocumentClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocumentClick))

onMounted(async () => {
  if (!topics.topics.length) await topics.load()
  if (!topic.value) return
  await topics.loadBrief(topicId.value)
  await chat.load(topicId.value)
  const queryId = String(route.query.conversation || '')
  const conversation = chat.conversations.find((item) => item.id === queryId) || chat.conversations[0]
  if (conversation) await selectConversation(conversation.id)
})

watch(
  () => [chat.messages.length, chat.messages[chat.messages.length - 1]?.content],
  async () => {
    await nextTick()
    if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
  },
)

async function selectConversation(id: string): Promise<void> {
  menuFor.value = ''
  await chat.open(id)
  if (route.query.conversation !== id) {
    await router.replace({ query: { ...route.query, conversation: id } })
  }
}

async function createConversation(): Promise<void> {
  const conversation = await chat.create(topicId.value)
  await selectConversation(conversation.id)
}

async function confirmDelete(): Promise<void> {
  if (!pendingDelete.value) return
  deleteBusy.value = true
  try {
    await chat.remove(pendingDelete.value.id)
    pendingDelete.value = null
    const next = chat.conversations[0]
    if (next) await selectConversation(next.id)
    else await router.replace({ query: { ...route.query, conversation: undefined } })
  } finally {
    deleteBusy.value = false
  }
}

async function send(text: string): Promise<void> {
  await chat.send(text)
}

function stop(): void {
  chat.stop()
}

function switchMode(mode: 'report' | 'chat'): void {
  void router.push(`/topics/${topicId.value}/${mode}`)
}

function timeAgo(iso: string): string {
  const minutes = Math.floor((Date.now() - new Date(iso).getTime()) / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}
</script>

<template>
  <div v-if="topic" class="chat-page">
    <TopicHeader
      :topic="topic"
      :brief="topics.briefs[topicId]"
      mode="chat"
      @back="router.push('/')"
      @update:mode="switchMode"
    />

    <div class="workspace" :style="{ gridTemplateColumns: `${layout.leftWidth}px minmax(0, 1fr)` }">
      <aside ref="menuRoot" class="conversations" :class="{ 'conversations--collapsed': layout.leftCollapsed }">
        <header>
          <h2 v-if="!layout.leftCollapsed">Conversations</h2>
          <div class="actions">
            <IconButton v-if="!layout.leftCollapsed" label="New conversation" @click="createConversation">+</IconButton>
            <IconButton :label="layout.leftCollapsed ? 'Expand conversations' : 'Collapse conversations'" @click="layout.toggleLeft">
              {{ layout.leftCollapsed ? '›' : '‹' }}
            </IconButton>
          </div>
        </header>

        <div v-if="!layout.leftCollapsed" class="conversations__body">
          <p v-if="chat.loading" class="state">Loading conversations…</p>
          <p v-else-if="!chat.conversations.length" class="state">No conversations yet.</p>
          <ul v-else class="conversation-list">
            <li
              v-for="conversation in chat.conversations"
              :key="conversation.id"
              class="conversation"
              :class="{ 'conversation--active': conversation.id === chat.activeId }"
            >
              <button type="button" class="conversation__main" @click="selectConversation(conversation.id)">
                <span class="conversation__title">{{ conversation.title }}</span>
                <span class="conversation__meta">{{ timeAgo(conversation.updated_at) }}</span>
              </button>
              <div class="conversation__menu">
                <button
                  type="button"
                  class="conversation__more"
                  aria-label="Conversation actions"
                  @click.stop="menuFor = menuFor === conversation.id ? '' : conversation.id"
                >⋯</button>
                <div v-if="menuFor === conversation.id" class="menu">
                  <button type="button" @click.stop="menuFor = ''; pendingDelete = conversation">Delete conversation</button>
                </div>
              </div>
            </li>
          </ul>
        </div>
      </aside>

      <main class="chat-main">
        <header class="chat-main__head">
          <div>
            <p class="chat-main__eyebrow">Chat</p>
            <h2>{{ chat.active?.title || 'Conversation' }}</h2>
          </div>
          <span v-if="chat.sending" class="streaming">Streaming…</span>
        </header>

        <div ref="scroller" class="messages">
          <p v-if="chat.loadingMessages" class="state">Loading messages…</p>
          <EmptyState
            v-else-if="!chat.messages.length"
            title="Start a conversation"
            description="Ask a question about this topic. The chat stays inside the topic scope."
          />
          <template v-else>
            <ChatMessageItem v-for="message in chat.messages" :key="message.id" :message="message" />
          </template>
          <p v-if="chat.error" class="error">{{ chat.error }}</p>
        </div>

        <ChatComposer
          :disabled="!chat.activeId || chat.loadingMessages"
          :sending="chat.sending"
          @send="send"
          @stop="stop"
        />
      </main>
    </div>

    <ConfirmDialog
      :open="Boolean(pendingDelete)"
      title="Delete this conversation?"
      message="This removes the conversation and its messages."
      confirm-text="Delete conversation"
      :busy="deleteBusy"
      @cancel="pendingDelete = null"
      @confirm="confirmDelete"
    />
  </div>

  <div v-else class="missing">
    <EmptyState title="Topic not found" description="This topic no longer exists or could not be loaded.">
      <Button size="sm" @click="router.push('/')">Back to topics</Button>
    </EmptyState>
  </div>
</template>

<style scoped>
.chat-page {
  height: 100%;
  padding-top: var(--topbar-h);
}

.workspace {
  display: grid;
  height: calc(100vh - var(--topbar-h));
  min-height: 0;
}

.conversations {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-right: 1px solid var(--border);
  background: var(--surface);
}

.conversations--collapsed {
  align-items: center;
}

.conversations header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  width: 100%;
  min-height: 48px;
  padding: 0 var(--space-3);
  border-bottom: 1px solid var(--border);
}

.conversations h2 {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 650;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.actions {
  display: flex;
  gap: 2px;
}

.conversations__body {
  min-height: 0;
  overflow: auto;
  padding: var(--space-2);
}

.state {
  padding: var(--space-3);
  color: var(--text-muted);
  font-size: 12px;
}

.conversation-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.conversation {
  position: relative;
  display: flex;
  border-radius: var(--radius-sm);
}

.conversation:hover,
.conversation--active {
  background: var(--surface-muted);
}

.conversation__main {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  min-width: 0;
  padding: 8px 8px 8px 10px;
  border: 0;
  background: transparent;
  text-align: left;
}

.conversation__title {
  overflow: hidden;
  width: 100%;
  font-size: 12px;
  font-weight: 550;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conversation__meta {
  color: var(--text-faint);
  font-size: 10px;
}

.conversation__menu {
  position: relative;
  display: flex;
  align-items: flex-start;
  padding-top: 4px;
}

.conversation__more {
  width: 24px;
  height: 24px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--text-faint);
}

.conversation__more:hover {
  background: var(--border);
  color: var(--text);
}

.menu {
  position: absolute;
  top: 28px;
  right: 0;
  z-index: 20;
  min-width: 150px;
  padding: 4px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  box-shadow: 0 8px 22px rgb(0 0 0 / 10%);
}

.menu button {
  width: 100%;
  padding: 7px 8px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--danger);
  font-size: 12px;
  text-align: left;
}

.menu button:hover {
  background: var(--danger-soft);
}

.chat-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  background: var(--surface);
}

.chat-main__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  padding: 18px 24px 12px;
  border-bottom: 1px solid var(--border);
}

.chat-main__eyebrow {
  margin-bottom: 2px;
  color: var(--text-faint);
  font-size: 10px;
  font-weight: 650;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.chat-main__head h2 {
  font-size: 17px;
  font-weight: 650;
}

.streaming {
  color: var(--accent);
  font-size: 11px;
}

.messages {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 12px 24px 24px;
}

.error {
  color: var(--danger);
  font-size: 12px;
}

.missing {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding-top: var(--topbar-h);
}
</style>
