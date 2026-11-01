<script setup lang="ts">
import { ref } from 'vue'
import Button from '@/components/ui/Button.vue'

defineProps<{
  disabled?: boolean
  sending?: boolean
}>()

const emit = defineEmits<{
  send: [text: string]
  stop: []
}>()

const text = ref('')
const input = ref<HTMLTextAreaElement | null>(null)

function submit(): void {
  const value = text.value.trim()
  if (!value) return
  emit('send', value)
  text.value = ''
  input.value?.focus()
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    submit()
  }
}
</script>

<template>
  <footer class="composer">
    <textarea
      ref="input"
      v-model="text"
      rows="2"
      placeholder="Ask about this topic…"
      :disabled="disabled"
      @keydown="onKeydown"
    />
    <div class="composer__actions">
      <span class="composer__hint">Enter to send · Shift+Enter for a new line</span>
      <Button v-if="sending" size="sm" variant="secondary" @click="emit('stop')">Stop</Button>
      <Button v-else size="sm" variant="primary" :disabled="disabled || !text.trim()" @click="submit">Send</Button>
    </div>
  </footer>
</template>

<style scoped>
.composer {
  padding: 12px 20px 18px;
  border-top: 1px solid var(--border);
  background: var(--surface);
}

textarea {
  width: 100%;
  max-height: 180px;
  padding: 9px 11px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-md);
  background: var(--surface);
  font-size: 13px;
  line-height: 1.5;
  resize: vertical;
}

.composer__actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: 7px;
}

.composer__hint {
  flex: 1;
  color: var(--text-faint);
  font-size: 10px;
}
</style>
