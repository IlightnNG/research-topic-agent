<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import type { PaperLink } from '@/types'

const props = defineProps<{
  text: string
  links?: PaperLink[]
}>()

const emit = defineEmits<{ openPaper: [paperId: string] }>()

const html = computed(() => {
  const raw = marked.parse(props.text || '', { gfm: true, breaks: false }) as string
  const clean = DOMPurify.sanitize(raw, { USE_PROFILES: { html: true } })
  const template = document.createElement('template')
  template.innerHTML = clean
  const linkMap = new Map((props.links ?? []).map((link) => [link.token.toLowerCase(), link]))
  const walker = document.createTreeWalker(template.content, NodeFilter.SHOW_TEXT)
  const nodes: Text[] = []
  while (walker.nextNode()) nodes.push(walker.currentNode as Text)
  for (const node of nodes) {
    const parent = node.parentElement?.tagName.toLowerCase()
    if (parent === 'code' || parent === 'pre') continue
    const parts = node.data.split(/(\[[A-Za-z0-9]+\])/g)
    if (!parts.some((part) => linkMap.has(part.slice(1, -1).toLowerCase()))) continue
    const fragment = document.createDocumentFragment()
    for (const part of parts) {
      const match = part.match(/^\[([A-Za-z0-9]+)\]$/)
      const link = match ? linkMap.get(match[1].toLowerCase()) : undefined
      if (!link) {
        fragment.appendChild(document.createTextNode(part))
        continue
      }
      const button = document.createElement('button')
      button.type = 'button'
      button.className = 'citation'
      button.dataset.paperId = link.paper_id
      button.title = `Open paper ${link.paper_id}`
      button.textContent = part
      fragment.appendChild(button)
    }
    node.replaceWith(fragment)
  }
  return template.innerHTML
})

function onClick(event: MouseEvent): void {
  const target = event.target as HTMLElement | null
  const button = target?.closest('button.citation') as HTMLButtonElement | null
  if (button?.dataset.paperId) emit('openPaper', button.dataset.paperId)
}
</script>

<template>
  <div class="body" @click="onClick" v-html="html"></div>
</template>

<style scoped>
.body {
  color: var(--text);
  font-size: 14px;
  line-height: 1.72;
}

.body :deep(h1),
.body :deep(h2),
.body :deep(h3) {
  margin: 18px 0 8px;
  color: var(--text);
  font-weight: 650;
  line-height: 1.3;
}

.body :deep(h1) {
  font-size: 21px;
}

.body :deep(h2) {
  font-size: 18px;
}

.body :deep(h3) {
  font-size: 15px;
}

.body :deep(p) {
  margin: 0 0 12px;
}

.body :deep(ul),
.body :deep(ol) {
  margin: 0 0 12px;
  padding-left: 22px;
}

.body :deep(li) {
  margin: 4px 0;
}

.body :deep(blockquote) {
  margin: 12px 0;
  padding: 6px 12px;
  border-left: 3px solid var(--border);
  color: var(--text-muted);
}

.body :deep(pre) {
  overflow-x: auto;
  padding: 10px 12px;
  border-radius: 6px;
  background: var(--surface-raised);
  font-family: var(--font-mono);
  font-size: 12px;
}

.body :deep(code) {
  padding: 1px 4px;
  border-radius: 3px;
  background: var(--surface-raised);
  font-family: var(--font-mono);
  font-size: 0.92em;
}

.body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  font-size: 12px;
}

.body :deep(th),
.body :deep(td) {
  border: 1px solid var(--border);
  padding: 6px 8px;
  text-align: left;
}

.body :deep(a) {
  color: var(--accent);
}

.body :deep(button.citation) {
  display: inline;
  padding: 0 2px;
  border: 0;
  border-radius: 3px;
  background: var(--accent-soft);
  color: var(--accent);
  cursor: pointer;
  font-family: var(--font-mono);
  font-size: 0.92em;
  line-height: inherit;
}
</style>
