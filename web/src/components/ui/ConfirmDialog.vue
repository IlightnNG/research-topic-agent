<script setup lang="ts">
import Button from './Button.vue'
import Modal from './Modal.vue'

withDefaults(
  defineProps<{
    open: boolean
    title: string
    message: string
    confirmText?: string
    cancelText?: string
    busy?: boolean
  }>(),
  { confirmText: 'Confirm', cancelText: 'Cancel', busy: false },
)

const emit = defineEmits<{ confirm: []; cancel: [] }>()
</script>

<template>
  <Modal :open="open" :title="title" :close-on-backdrop="!busy" @close="emit('cancel')">
    <p class="message">{{ message }}</p>
    <template #footer>
      <Button variant="secondary" :disabled="busy" @click="emit('cancel')">{{ cancelText }}</Button>
      <Button variant="danger" :disabled="busy" @click="emit('confirm')">
        {{ busy ? 'Working…' : confirmText }}
      </Button>
    </template>
  </Modal>
</template>

<style scoped>
.message {
  color: var(--text-muted);
  white-space: pre-line;
}
</style>
