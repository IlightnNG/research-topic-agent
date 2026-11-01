import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import type { CreateTopicInput, Topic, TopicBrief } from '@/types'

export const useTopicsStore = defineStore('topics', () => {
  const topics = ref<Topic[]>([])
  const briefs = ref<Record<string, TopicBrief>>({})
  const loading = ref(false)
  const error = ref('')

  const byId = computed(() => Object.fromEntries(topics.value.map((topic) => [topic.id, topic])))

  async function load(): Promise<void> {
    loading.value = true
    error.value = ''
    try {
      topics.value = await api.listTopics()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Could not load topics.'
    } finally {
      loading.value = false
    }
  }

  async function create(input: CreateTopicInput): Promise<Topic> {
    const topic = await api.createTopic(input)
    topics.value = [topic, ...topics.value]
    return topic
  }

  async function loadBrief(topicId: string): Promise<void> {
    if (briefs.value[topicId]) return
    const brief = await api.getTopicBrief(topicId)
    if (brief) briefs.value[topicId] = brief
  }

  return { topics, briefs, loading, error, byId, load, create, loadBrief }
})
