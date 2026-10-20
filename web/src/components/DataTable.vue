<script setup lang="ts" generic="T extends Record<string, unknown>">
defineProps<{
  columns: Array<{ key: string; label: string; width?: number }>;
  rows: T[];
  emptyText?: string;
}>();
</script>

<template>
  <el-table :data="rows" size="small" :empty-text="emptyText ?? '暂无数据'">
    <el-table-column
      v-for="column in columns"
      :key="column.key"
      :prop="column.key"
      :label="column.label"
      :width="column.width"
    >
      <template #default="scope">
        <slot :name="`cell-${column.key}`" :row="scope.row">
          {{ scope.row[column.key] }}
        </slot>
      </template>
    </el-table-column>
  </el-table>
</template>
