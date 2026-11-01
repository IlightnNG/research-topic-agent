<script setup lang="ts">
import type { Topic } from '@/types'
import Button from '@/components/ui/Button.vue'

defineProps<{
  topic: Topic
}>()

const emit = defineEmits<{
  report: [topic: Topic]
  chat: [topic: Topic]
}>()
</script>

<template>
  <article class="topic-card">
    <header>
      <div class="topic-card__mark" aria-hidden="true">{{ topic.direction.slice(0, 2).toUpperCase() }}</div>
      <div>
        <h2>{{ topic.direction }}</h2>
        <p v-if="topic.description">{{ topic.description }}</p>
      </div>
    </header>
    <div v-if="topic.keywords?.length" class="topic-card__tags">
      <span v-for="keyword in topic.keywords.slice(0, 4)" :key="keyword">{{ keyword }}</span>
    </div>
    <footer>
      <Button size="sm" variant="primary" @click="emit('report', topic)">Report</Button>
      <Button size="sm" variant="secondary" @click="emit('chat', topic)">Chat</Button>
    </footer>
  </article>
</template>

<style scoped>
.topic-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-height: 190px;
  padding: var(--space-5);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
  box-shadow: var(--shadow-sm);
  transition: border-color 120ms ease, transform 120ms ease;
}

.topic-card:hover {
  border-color: var(--border-strong);
  transform: translateY(-1px);
}

.topic-card header {
  display: flex;
  gap: var(--space-3);
}

.topic-card__mark {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 38px;
  height: 38px;
  border-radius: var(--radius-sm);
  background: var(--accent-soft);
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 650;
}

.topic-card h2 {
  margin-bottom: 4px;
  font-size: 16px;
  font-weight: 650;
}

.topic-card p {
  color: var(--text-muted);
  font-size: 13px;
  line-height: 1.5;
}

.topic-card__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.topic-card__tags span {
  padding: 2px 7px;
  border-radius: 999px;
  background: var(--surface-muted);
  color: var(--text-muted);
  font-size: 11px;
}

.topic-card footer {
  display: flex;
  gap: var(--space-2);
  margin-top: auto;
}
</style>
