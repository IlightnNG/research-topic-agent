<script setup lang="ts">
import type { PaperLink } from '@/types'

const props = defineProps<{
  text: string
  links?: PaperLink[]
}>()

const emit = defineEmits<{
  openPaper: [paperId: string]
}>()

interface Part {
  text: string
  link?: PaperLink
}

function parts(): Part[] {
  const map = new Map((props.links ?? []).map((link) => [link.token.toLowerCase(), link]))
  return props.text
    .split(/(\[[A-Za-z0-9]+\])/g)
    .filter(Boolean)
    .map((part) => {
      const match = part.match(/^\[([A-Za-z0-9]+)\]$/)
      if (!match) return { text: part }
      return { text: part, link: map.get(match[1].toLowerCase()) }
    })
}
</script>

<template>
  <span class="citation-text">
    <template v-for="(part, index) in parts()" :key="index">
      <button
        v-if="part.link"
        type="button"
        class="citation"
        :title="`Open paper ${part.link.paper_id}`"
        @click="emit('openPaper', part.link!.paper_id)"
      >{{ part.text }}</button>
      <span v-else>{{ part.text }}</span>
    </template>
  </span>
</template>

<style scoped>
.citation {
  display: inline;
  padding: 0 2px;
  border: 0;
  border-radius: 3px;
  background: var(--accent-soft);
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 0.92em;
  line-height: inherit;
}

.citation:hover {
  background: #d7e7f1;
  text-decoration: underline;
}
</style>
