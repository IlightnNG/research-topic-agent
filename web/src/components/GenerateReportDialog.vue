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
    title="生成新周报"
    confirm-text="开始生成"
    :busy="busy"
    :error-text="errorText"
    @update:model-value="emit('update:modelValue', $event)"
    @confirm="emit('submit', hint.trim() ? hint.trim() : null)"
  >
    <p class="muted">源与时间窗沿用 topic 设定；这里只填本次的聚焦提示（可选）。</p>
    <el-input
      v-model="hint"
      maxlength="120"
      show-word-limit
      placeholder="例如：LLM agent 的工具使用与评测"
    />
  </DialogForm>
</template>
