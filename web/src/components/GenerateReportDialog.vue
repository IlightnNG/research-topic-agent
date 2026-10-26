<script setup lang="ts">
import { ref, watch } from "vue";

import DialogForm from "./DialogForm.vue";

const props = defineProps<{ modelValue: boolean; busy?: boolean; errorText?: string }>();
const emit = defineEmits<{
  "update:modelValue": [boolean];
  submit: [string | null];
}>();

const hint = ref("");

watch(
  () => props.modelValue,
  (open) => {
    if (open) hint.value = "";
  },
);
</script>

<template>
  <DialogForm
    :model-value="modelValue"
    title="Generate report"
    confirm-text="Start"
    :busy="busy"
    :error-text="errorText"
    @update:model-value="emit('update:modelValue', $event)"
    @confirm="emit('submit', hint.trim() ? hint.trim() : null)"
  >
    <p class="muted">Source and time window come from the topic; only set an optional focus hint.</p>
    <el-input
      v-model="hint"
      maxlength="120"
      show-word-limit
      placeholder="e.g. tool use and evaluation of LLM agents"
    />
  </DialogForm>
</template>
