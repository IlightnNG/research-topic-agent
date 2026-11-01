import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

export const useLayoutStore = defineStore('layout', () => {
  const leftCollapsed = ref(localStorage.getItem('lit-left-collapsed') === 'true')
  const rightCollapsed = ref(localStorage.getItem('lit-right-collapsed') !== 'false')

  const leftWidth = computed(() => (leftCollapsed.value ? 48 : 248))

  function toggleLeft(): void {
    leftCollapsed.value = !leftCollapsed.value
    localStorage.setItem('lit-left-collapsed', String(leftCollapsed.value))
  }

  function toggleRight(): void {
    rightCollapsed.value = !rightCollapsed.value
    localStorage.setItem('lit-right-collapsed', String(rightCollapsed.value))
  }

  return { leftCollapsed, rightCollapsed, leftWidth, toggleLeft, toggleRight }
})
