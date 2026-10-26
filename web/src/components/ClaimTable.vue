<script setup lang="ts">
import type { Claim } from "@/api/types";

import StatusBadge from "./StatusBadge.vue";

defineProps<{ claims: Claim[] }>();
const emit = defineEmits<{ why: [number] }>();
</script>

<template>
  <el-table :data="claims" size="small" empty-text="No claims">
    <el-table-column type="expand">
      <template #default="scope">
        <div class="stack" style="padding: var(--space-2) var(--space-4)">
          <p class="muted">citations</p>
          <ul>
            <li v-for="(citation, index) in scope.row.citations" :key="index" class="mono">
              {{ citation.paper_id }}
              <span v-if="citation.snippet" class="muted">— {{ citation.snippet }}</span>
            </li>
          </ul>
        </div>
      </template>
    </el-table-column>
    <el-table-column type="index" label="#" width="48" />
    <el-table-column prop="text" label="claim" />
    <el-table-column label="support" width="130">
      <template #default="scope">
        <StatusBadge
          :state="scope.row.support === 'supported' ? 'ok' : 'degraded'"
          :label="scope.row.support"
        />
      </template>
    </el-table-column>
    <el-table-column label="Citations" width="80">
      <template #default="scope">{{ scope.row.citations?.length ?? 0 }}</template>
    </el-table-column>
    <el-table-column label="" width="90">
      <template #default="scope">
        <el-button text size="small" @click="emit('why', scope.$index)">Why</el-button>
      </template>
    </el-table-column>
  </el-table>
</template>
