<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import type { CreateTopicInput } from '@/types'
import Button from '@/components/ui/Button.vue'
import Modal from '@/components/ui/Modal.vue'

const props = defineProps<{
  open: boolean
  busy?: boolean
  error?: string
}>()

const emit = defineEmits<{
  close: []
  create: [input: CreateTopicInput]
}>()

const form = reactive({
  direction: '',
  description: '',
  keywords: '',
  exclusions: '',
  constraints: '',
})
const localError = ref('')

function split(value: string): string[] | undefined {
  const items = value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
  return items.length ? items : undefined
}

function submit(): void {
  if (!form.direction.trim()) {
    localError.value = 'Direction is required.'
    return
  }
  localError.value = ''
  emit('create', {
    direction: form.direction.trim(),
    description: form.description.trim() || undefined,
    keywords: split(form.keywords),
    exclusions: split(form.exclusions),
    constraints: split(form.constraints),
  })
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      form.direction = ''
      form.description = ''
      form.keywords = ''
      form.exclusions = ''
      form.constraints = ''
      localError.value = ''
    }
  },
)
</script>

<template>
  <Modal :open="open" title="New Topic" :close-on-backdrop="!busy" @close="emit('close')">
    <form class="form" @submit.prevent="submit">
      <label>
        <span>Direction <em>required</em></span>
        <input v-model="form.direction" placeholder="e.g. AI agents, FPGA acceleration" />
      </label>
      <label>
        <span>Description</span>
        <textarea v-model="form.description" rows="3" placeholder="What belongs in this topic?" />
      </label>
      <div class="form__row">
        <label>
          <span>Keywords</span>
          <input v-model="form.keywords" placeholder="tool use, planning" />
        </label>
        <label>
          <span>Exclusions</span>
          <input v-model="form.exclusions" placeholder="robotics control" />
        </label>
      </div>
      <label>
        <span>Constraints</span>
        <input v-model="form.constraints" placeholder="peer reviewed, 2020+" />
      </label>
      <p class="hint">
        Direction is the hard scope boundary. The agent may refine it into a normalized
        research brief, but must not broaden it.
      </p>
      <p v-if="localError || error" class="error">{{ localError || error }}</p>
    </form>
    <template #footer>
      <Button variant="secondary" :disabled="busy" @click="emit('close')">Cancel</Button>
      <Button variant="primary" :disabled="busy" @click="submit">
        {{ busy ? 'Creating…' : 'Create Topic' }}
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

.form__row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
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

input,
textarea {
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

.hint {
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.error {
  color: var(--danger);
  font-size: 12px;
}
</style>
