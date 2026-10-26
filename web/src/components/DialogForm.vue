<script setup lang="ts">
defineProps<{
  modelValue: boolean;
  title: string;
  confirmText?: string;
  busy?: boolean;
  errorText?: string;
}>();
const emit = defineEmits<{ "update:modelValue": [boolean]; confirm: [] }>();

function close(): void {
  emit("update:modelValue", false);
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="title"
    width="480px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="stack">
      <slot />
      <el-alert v-if="errorText" type="error" :closable="false" :title="errorText" />
    </div>
    <template #footer>
      <div class="cluster" style="justify-content: flex-end">
        <el-button @click="close">Cancel</el-button>
        <el-button type="primary" :loading="busy" @click="emit('confirm')">
          {{ confirmText ?? "OK" }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>
