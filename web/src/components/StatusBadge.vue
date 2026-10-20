<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{ state?: string | null; label?: string; tone?: "success" | "warning" | "danger" | "info" }>();

const TONES: Record<string, "success" | "warning" | "danger" | "info" | "primary"> = {
  succeeded: "success",
  running: "primary",
  queued: "info",
  failed: "danger",
  aborted: "info",
  degraded: "warning",
  warning: "warning",
  ok: "success",
  archived: "info",
};

const type = computed(() => props.tone ?? TONES[props.state ?? ""] ?? "info");
const text = computed(() => props.label ?? props.state ?? "unknown");
</script>

<template>
  <el-tag :type="type" disable-transitions size="small" effect="light">{{ text }}</el-tag>
</template>
