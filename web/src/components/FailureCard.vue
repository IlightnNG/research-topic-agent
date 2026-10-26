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
  <SectionCard title="This run did not succeed" subtitle="Error / last stage / period / next action">
    <div class="stack">
      <StatusBadge :state="run?.state ?? 'failed'" />
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="Error">{{ errorCode ?? "unknown" }}</el-descriptions-item>
        <el-descriptions-item label="State">{{ run?.state ?? "-" }}</el-descriptions-item>
        <el-descriptions-item label="Last stage">{{ run?.stage ?? "-" }}</el-descriptions-item>
        <el-descriptions-item label="Period">{{ run?.period ?? "-" }}</el-descriptions-item>
      </el-descriptions>
      <div class="cluster">
        <el-button type="primary" size="small" @click="emit('retry')">Retry</el-button>
        <el-button size="small" @click="details = !details">Show details</el-button>
      </div>
      <pre v-if="details" class="mono">{{ JSON.stringify(run, null, 2) }}</pre>
    </div>
  </SectionCard>
</template>
