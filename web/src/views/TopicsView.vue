<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useTopicsStore } from '@/stores/topics'
import type { CreateTopicInput, Topic } from '@/types'
import Button from '@/components/ui/Button.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import TopicCard from '@/components/topics/TopicCard.vue'
import NewTopicModal from '@/components/topics/NewTopicModal.vue'

const router = useRouter()
const store = useTopicsStore()
const modalOpen = ref(false)
const busy = ref(false)
const createError = ref('')

onMounted(() => {
  if (!store.topics.length) void store.load()
})

async function createTopic(input: CreateTopicInput): Promise<void> {
  busy.value = true
  createError.value = ''
  try {
    const topic = await store.create(input)
    modalOpen.value = false
    await router.push(`/topics/${topic.id}/report`)
  } catch (error) {
    createError.value = error instanceof Error ? error.message : 'Could not create topic.'
  } finally {
    busy.value = false
  }
}

function openReport(topic: Topic): void {
  void router.push(`/topics/${topic.id}/report`)
}

function openChat(topic: Topic): void {
  void router.push(`/topics/${topic.id}/chat`)
}
</script>

<template>
  <div class="topics-page">
    <header class="page-head">
      <div>
        <p class="eyebrow">Research workspace</p>
        <h1>Topics</h1>
        <p class="sub">Choose a direction, then generate a report or start a conversation.</p>
      </div>
      <Button variant="primary" @click="modalOpen = true">+ New Topic</Button>
    </header>

    <p v-if="store.error" class="error">{{ store.error }}</p>
    <p v-if="store.loading" class="loading">Loading topics…</p>

    <div v-else-if="store.topics.length" class="topic-grid">
      <TopicCard
        v-for="topic in store.topics"
        :key="topic.id"
        :topic="topic"
        @report="openReport"
        @chat="openChat"
      />
    </div>

    <EmptyState
      v-else
      title="No topics yet"
      description="Create a topic to define the research direction the agent must stay inside."
    >
      <Button variant="primary" size="sm" @click="modalOpen = true">Create your first topic</Button>
    </EmptyState>

    <NewTopicModal
      :open="modalOpen"
      :busy="busy"
      :error="createError"
      @close="modalOpen = false"
      @create="createTopic"
    />
  </div>
</template>

<style scoped>
.topics-page {
  max-width: 1180px;
  margin: 0 auto;
  padding: 52px 32px 80px;
}

.page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-5);
  margin-bottom: 30px;
}

.eyebrow {
  margin-bottom: 5px;
  color: var(--text-faint);
  font-size: 10px;
  font-weight: 650;
  letter-spacing: 0.07em;
  text-transform: uppercase;
}

.page-head h1 {
  font-size: 30px;
  font-weight: 680;
  letter-spacing: -0.02em;
}

.sub {
  margin-top: 5px;
  color: var(--text-muted);
  font-size: 14px;
}

.topic-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-4);
}

.error {
  color: var(--danger);
  font-size: 13px;
}

.loading {
  color: var(--text-muted);
}

@media (max-width: 980px) {
  .topic-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 680px) {
  .topics-page {
    padding: 32px 18px 60px;
  }

  .page-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .topic-grid {
    grid-template-columns: 1fr;
  }
}
</style>
