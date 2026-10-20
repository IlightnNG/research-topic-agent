<script setup lang="ts">
import { ElMessage } from "element-plus";
import { computed } from "vue";

import { describeError } from "@/api/client";

const props = defineProps<{ code?: string; message?: string; error?: unknown; retryable?: boolean }>();
const emit = defineEmits<{ retry: [] }>();

const text = computed(() => props.message ?? describeError(props.error) ?? "Unknown error");
const canRetry = computed(() => props.retryable ?? true);
</script>

<template>
  <el-alert type="error" :closable="false" show-icon :title="code ? `${code}: ${text}` : text">
    <template #default>
      <div class="cluster">
        <el-button v-if="canRetry" size="small" @click="emit('retry')">重试</el-button>
        <el-button size="small" text @click="ElMessage.info('已记录到日志')">查看日志</el-button>
      </div>
    </template>
  </el-alert>
</template>
