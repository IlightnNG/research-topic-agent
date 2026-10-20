<script setup lang="ts">
import { ref } from "vue";

import type { RunDetail } from "@/api/types";

import SectionCard from "./SectionCard.vue";
import StatusBadge from "./StatusBadge.vue";

defineProps<{ run: RunDetail | null; errorCode?: string | null }>();
const emit = defineEmits<{ retry: [] }>();
const details = ref(false);
</script>

<template>
  <SectionCard title="本次运行未成功" subtitle="错误码 / 最后阶段 / 周期 / 建议动作">
    <div class="stack">
      <StatusBadge :state="run?.state ?? 'failed'" />
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="错误码">{{ errorCode ?? "unknown" }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ run?.state ?? "-" }}</el-descriptions-item>
        <el-descriptions-item label="最后阶段">{{ run?.stage ?? "-" }}</el-descriptions-item>
        <el-descriptions-item label="周期">{{ run?.period ?? "-" }}</el-descriptions-item>
      </el-descriptions>
      <div class="cluster">
        <el-button type="primary" size="small" @click="emit('retry')">重跑</el-button>
        <el-button size="small" @click="details = !details">查看详情</el-button>
      </div>
      <pre v-if="details" class="mono">{{ JSON.stringify(run, null, 2) }}</pre>
    </div>
  </SectionCard>
</template>
