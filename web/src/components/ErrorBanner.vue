<script setup lang="ts">
import { ElMessage } from "element-plus";
import { computed } from "vue";

import { describeError } from "@/api/client";
import { humanize, isRetryable } from "@/api/errors";

const props = defineProps<{ code?: string; message?: string; error?: unknown; retryable?: boolean }>();
const emit = defineEmits<{ retry: [] }>();

const raw = computed(() => props.message ?? describeError(props.error) ?? "Unknown error");
const text = computed(() => humanize(props.code, raw.value));
const canRetry = computed(() => props.retryable ?? isRetryable(props.code));
</script>

<template>
  <el-alert type="error" :closable="false" show-icon :title="text">
    <template #default>
      <div class="cluster">
        <el-button v-if="canRetry" size="small" @click="emit('retry')">重试</el-button>
        <el-button size="small" text @click="ElMessage.info(raw)">详情</el-button>
      </div>
    </template>
  </el-alert>
</template>
