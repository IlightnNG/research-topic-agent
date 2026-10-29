<script setup lang="ts">
import { ref, watch } from "vue";

import DialogForm from "./DialogForm.vue";

const props = defineProps<{ modelValue: boolean; busy?: boolean; errorText?: string }>();
const emit = defineEmits<{
  "update:modelValue": [boolean];
  submit: [string | null, "en" | "zh"];
}>();

const hint = ref("");
const language = ref<"en" | "zh">("en");

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      hint.value = "";
      language.value = "en";
    }
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
    @confirm="emit('submit', hint.trim() ? hint.trim() : null, language)"
  >
    <p class="muted">Source and time window come from the topic; only set an optional focus hint.</p>
    <el-input
      v-model="hint"
      maxlength="120"
      show-word-limit
      placeholder="e.g. tool use and evaluation of LLM agents"
    />
    <label class="muted" for="report-language">Report language</label>
    <el-select id="report-language" v-model="language" style="width: 180px">
      <el-option label="English" value="en" />
      <el-option label="中文" value="zh" />
    </el-select>
  </DialogForm>
</template>
