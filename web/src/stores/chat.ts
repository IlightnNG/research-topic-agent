import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import type { ChatMessage, Conversation } from '@/types'

export const useChatStore = defineStore('chat', () => {
  const conversations = ref<Conversation[]>([])
  const activeId = ref('')
  const messages = ref<ChatMessage[]>([])
  const loading = ref(false)
  const loadingMessages = ref(false)
  const sending = ref(false)
  const error = ref('')
  let controller: AbortController | undefined

  const active = computed(() => conversations.value.find((item) => item.id === activeId.value))

  async function load(topicId: string): Promise<void> {
    loading.value = true
    error.value = ''
    try {
      conversations.value = await api.listConversations(topicId)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Could not load conversations.'
    } finally {
      loading.value = false
    }
  }

  async function open(conversationId: string): Promise<void> {
    activeId.value = conversationId
    loadingMessages.value = true
    error.value = ''
    try {
      messages.value = (await api.getMessages(conversationId)).map((message) => ({
        ...message,
        state: 'done',
      }))
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Could not load messages.'
    } finally {
      loadingMessages.value = false
    }
  }

  async function create(topicId: string): Promise<Conversation> {
    const conversation = await api.createConversation(topicId)
    conversations.value = [conversation, ...conversations.value]
    activeId.value = conversation.id
    messages.value = []
    return conversation
  }

  async function remove(conversationId: string): Promise<void> {
    await api.deleteConversation(conversationId)
    conversations.value = conversations.value.filter((item) => item.id !== conversationId)
    if (activeId.value === conversationId) {
      const next = conversations.value[0]
      activeId.value = next?.id ?? ''
      messages.value = []
      if (next) await open(next.id)
    }
  }

  async function send(text: string): Promise<void> {
    const content = text.trim()
    if (!content || !activeId.value || sending.value) return
    const conversationId = activeId.value
    const now = new Date().toISOString()
    const user: ChatMessage = {
      id: `local-user-${Date.now()}`,
      conversation_id: conversationId,
      role: 'user',
      content,
      created_at: now,
      state: 'done',
    }
    const assistant: ChatMessage = {
      id: `local-assistant-${Date.now()}`,
      conversation_id: conversationId,
      role: 'assistant',
      content: '',
      created_at: now,
      state: 'streaming',
    }
    messages.value = [...messages.value, user, assistant]
    const assistantIndex = messages.value.length - 1
    sending.value = true
    error.value = ''
    controller = new AbortController()
    try {
      const result = await api.sendMessage(
        conversationId,
        content,
        (chunk) => {
          messages.value[assistantIndex].content += chunk
        },
        controller.signal,
      )
      messages.value[assistantIndex].content = result.content || messages.value[assistantIndex].content
      messages.value[assistantIndex].state = 'done'
      const conversation = conversations.value.find((item) => item.id === conversationId)
      if (conversation) {
        conversation.updated_at = new Date().toISOString()
        if (conversation.title === 'New conversation') conversation.title = content.slice(0, 44)
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        messages.value[assistantIndex].state = 'stopped'
      } else {
        messages.value[assistantIndex].state = 'error'
        error.value = err instanceof Error ? err.message : 'Message failed.'
      }
    } finally {
      sending.value = false
      controller = undefined
    }
  }

  function stop(): void {
    controller?.abort()
  }

  return {
    conversations,
    activeId,
    active,
    messages,
    loading,
    loadingMessages,
    sending,
    error,
    load,
    open,
    create,
    remove,
    send,
    stop,
  }
})
