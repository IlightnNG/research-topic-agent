<script setup lang="ts">
import type { ChatMessage } from '@/types'

defineProps<{
  message: ChatMessage
}>()
</script>

<template>
  <article class="message" :class="`message--${message.role}`">
    <div class="message__avatar" aria-hidden="true">{{ message.role === 'user' ? 'U' : 'A' }}</div>
    <div class="message__body">
      <p class="message__role">{{ message.role === 'user' ? 'You' : 'Agent' }}</p>
      <p v-if="message.content" class="message__content">{{ message.content }}</p>
      <p v-else-if="message.state === 'streaming'" class="message__typing">Thinking…</p>
      <p v-if="message.state === 'stopped'" class="message__state">Stopped.</p>
      <p v-if="message.state === 'error'" class="message__state message__state--error">Message failed.</p>
    </div>
  </article>
</template>

<style scoped>
.message {
  display: flex;
  gap: 11px;
  max-width: 760px;
  padding: 14px 0;
}

.message--user {
  margin-left: auto;
  flex-direction: row-reverse;
}

.message__avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--surface-muted);
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 650;
}

.message--user .message__avatar {
  background: var(--accent-soft);
  color: var(--accent);
}

.message__body {
  min-width: 0;
  max-width: 88%;
}

.message__role {
  margin-bottom: 3px;
  color: var(--text-faint);
  font-size: 10px;
  font-weight: 650;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.message--user .message__role {
  text-align: right;
}

.message__content {
  padding: 9px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
  color: var(--text);
  font-size: 13px;
  line-height: 1.65;
  white-space: pre-wrap;
}

.message--user .message__content {
  border-color: transparent;
  background: var(--accent-soft);
}

.message__typing {
  color: var(--text-faint);
  font-size: 12px;
  font-style: italic;
}

.message__state {
  margin-top: 3px;
  color: var(--text-faint);
  font-size: 10px;
}

.message__state--error {
  color: var(--danger);
}
</style>
