<script setup lang="ts">
import { computed } from 'vue'
import type { PaperLink } from '@/types'
import CitationText from './CitationText.vue'

const props = defineProps<{
  text: string
  links?: PaperLink[]
}>()

const emit = defineEmits<{ openPaper: [paperId: string] }>()

interface Block {
  type: 'heading1' | 'heading2' | 'heading3' | 'paragraph'
  text: string
}

const blocks = computed<Block[]>(() =>
  props.text
    .split(/\n{2,}/)
    .map((raw) => raw.trim())
    .filter(Boolean)
    .map((raw) => {
      if (raw.startsWith('### ')) return { type: 'heading3', text: raw.slice(4) }
      if (raw.startsWith('## ')) return { type: 'heading2', text: raw.slice(3) }
      if (raw.startsWith('# ')) return { type: 'heading1', text: raw.slice(2) }
      return { type: 'paragraph', text: raw }
    }),
)
</script>

<template>
  <div class="body">
    <template v-for="(block, index) in blocks" :key="index">
      <h3 v-if="block.type === 'heading3'">{{ block.text }}</h3>
      <h2 v-else-if="block.type === 'heading2'">{{ block.text }}</h2>
      <h1 v-else-if="block.type === 'heading1'">{{ block.text }}</h1>
      <p v-else>
        <CitationText :text="block.text" :links="links" @open-paper="emit('openPaper', $event)" />
      </p>
    </template>
  </div>
</template>

<style scoped>
.body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

h1,
h2,
h3 {
  margin: 0;
  font-weight: 650;
  line-height: 1.3;
}

h1 {
  font-size: 21px;
}

h2 {
  margin-top: 10px;
  font-size: 18px;
}

h3 {
  margin-top: 4px;
  font-size: 15px;
}

p {
  margin: 0;
  color: var(--text);
  font-size: 14px;
  line-height: 1.72;
  white-space: pre-wrap;
}
</style>
