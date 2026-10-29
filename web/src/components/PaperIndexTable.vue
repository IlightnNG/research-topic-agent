<script setup lang="ts">
import { computed, ref } from "vue";

import type { ReportSection } from "@/api/types";

const props = defineProps<{ section: ReportSection }>();
const emit = defineEmits<{ "open-paper": [string] }>();

const page = ref(1);
const pageSize = 20;

const rows = computed(() => {
  return props.section.body
    .split("\n")
    .filter((line) => line.trim().startsWith("|"))
    .slice(2)
    .map((line) =>
      line
        .split("|")
        .slice(1, -1)
        .map((cell) => cell.trim()),
    )
    .filter((cells) => cells.length >= 3 && cells[0]);
});

const visible = computed(() => rows.value.slice((page.value - 1) * pageSize, page.value * pageSize));
</script>

<template>
  <div class="stack">
    <el-table :data="visible" size="small" stripe>
      <el-table-column label="Paper" min-width="90">
        <template #default="{ row }">
          <el-button link type="primary" @click="emit('open-paper', row[0])">{{ row[0] }}</el-button>
        </template>
      </el-table-column>
      <el-table-column label="Title" min-width="360">
        <template #default="{ row }">{{ row[1] }}</template>
      </el-table-column>
      <el-table-column label="Claims" width="90">
        <template #default="{ row }">{{ row[2] }}</template>
      </el-table-column>
    </el-table>
    <el-pagination
      v-if="rows.length > pageSize"
      v-model:current-page="page"
      :page-size="pageSize"
      :total="rows.length"
      layout="prev, pager, next, total"
      small
    />
  </div>
</template>
