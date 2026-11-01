<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    width?: number
    closeOnBackdrop?: boolean
  }>(),
  { width: 480, closeOnBackdrop: true },
)

const emit = defineEmits<{
  close: []
}>()

const panel = ref<HTMLElement | null>(null)

function close(): void {
  emit('close')
}

function onKeydown(event: KeyboardEvent): void {
  if (!props.open) return
  if (event.key === 'Escape') close()
  if (event.key !== 'Tab' || !panel.value) return
  const focusable = panel.value.querySelectorAll<HTMLElement>(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
  )
  if (!focusable.length) return
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      document.addEventListener('keydown', onKeydown)
      nextTick(() => panel.value?.querySelector<HTMLElement>('input, textarea, select, button')?.focus())
    } else {
      document.removeEventListener('keydown', onKeydown)
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="backdrop" @click.self="closeOnBackdrop && close()">
      <section
        ref="panel"
        class="modal"
        role="dialog"
        aria-modal="true"
        :aria-label="title"
        :style="{ width: `${width}px` }"
      >
        <header class="modal__head">
          <h2>{{ title }}</h2>
          <button type="button" class="modal__close" aria-label="Close" @click="close">×</button>
        </header>
        <div class="modal__body">
          <slot />
        </div>
        <footer v-if="$slots.footer" class="modal__foot">
          <slot name="footer" />
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.backdrop {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-5);
  background: rgb(20 24 28 / 38%);
}

.modal {
  max-width: calc(100vw - 32px);
  max-height: calc(100vh - 64px);
  overflow: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: 0 18px 50px rgb(0 0 0 / 18%);
}

.modal__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px 12px;
}

.modal__head h2 {
  font-size: 18px;
  font-weight: 650;
}

.modal__close {
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-muted);
  font-size: 20px;
}

.modal__close:hover {
  background: var(--surface-muted);
}

.modal__body {
  padding: 4px 20px 20px;
}

.modal__foot {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  padding: 14px 20px;
  border-top: 1px solid var(--border);
  background: var(--surface-muted);
}
</style>
