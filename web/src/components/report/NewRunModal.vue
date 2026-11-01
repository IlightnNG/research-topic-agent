<script setup lang="ts">
import { reactive, watch } from 'vue'
import type { CreateRunInput, ReportLanguage } from '@/types'
import Button from '@/components/ui/Button.vue'
import Modal from '@/components/ui/Modal.vue'

const props = defineProps<{
  open: boolean
  busy?: boolean
  error?: string
  defaultLanguage?: ReportLanguage
}>()

const emit = defineEmits<{
  close: []
  create: [input: CreateRunInput]
}>()

const form = reactive({
  focus_hint: '',
  language: 'en' as ReportLanguage,
})

function submit(): void {
  emit('create', {
    focus_hint: form.focus_hint.trim() || null,
    language: form.language,
  })
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      form.focus_hint = ''
      form.language = props.defaultLanguage ?? 'en'
    }
  },
)
</script>

<template>
  <Modal :open="open" title="New Report Run" :close-on-backdrop="!busy" @close="emit('close')">
    <form class="form" @submit.prevent="submit">
      <label>
        <span>Research focus <em>optional</em></span>
        <textarea
          v-model="form.focus_hint"
          rows="4"
          placeholder="e.g. multi-agent evaluation, RAG citation quality, low-latency FPGA inference"
        />
        <small>Leave blank to use the topic's normalized direction. The focus must stay inside it.</small>
      </label>
      <label>
        <span>Report language</span>
        <select v-model="form.language">
          <option value="en">English</option>
          <option value="zh">Chinese</option>
        </select>
      </label>
      <p v-if="error" class="error">{{ error }}</p>
    </form>
    <template #footer>
      <Button variant="secondary" :disabled="busy" @click="emit('close')">Cancel</Button>
      <Button variant="primary" :disabled="busy" @click="submit">
        {{ busy ? 'Creating…' : 'Create Run' }}
      </Button>
    </template>
  </Modal>
</template>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

label {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

label > span {
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

label em {
  color: var(--text-faint);
  font-style: normal;
  font-weight: 400;
  text-transform: none;
}

textarea,
select {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm);
  background: var(--surface);
  font-size: 13px;
}

textarea {
  resize: vertical;
}

small {
  color: var(--text-muted);
  font-size: 11px;
  line-height: 1.5;
}

.error {
  color: var(--danger);
  font-size: 12px;
}
</style>
