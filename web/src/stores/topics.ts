import { defineStore } from "pinia";
import { ref } from "vue";

import { api } from "@/api/endpoints";
import { describeError } from "@/api/client";
import type { Topic } from "@/api/types";

export const useTopicsStore = defineStore("topics", () => {
  const items = ref<Topic[]>([]);
  const current = ref<Topic | null>(null);
  const counts = ref<Record<string, { runs: number; reports: number }>>({});
  const loading = ref(false);
  const error = ref("");

  async function load(): Promise<void> {
    loading.value = true;
    error.value = "";
    try {
      items.value = await api.listTopics();
      await Promise.all(items.value.map(loadCounts));
    } catch (err) {
      error.value = describeError(err);
    } finally {
      loading.value = false;
    }
  }

  async function loadCounts(topic: Topic): Promise<void> {
    try {
      counts.value[topic.id] = await api.topicCounts(topic.id);
    } catch {
      counts.value[topic.id] = { runs: 0, reports: 0 };
    }
  }

  async function loadOne(topicId: string): Promise<void> {
    current.value = await api.getTopic(topicId);
  }

  async function create(body: Record<string, unknown>): Promise<void> {
    await api.createTopic(body);
    await load();
  }

  async function patch(topicId: string, body: Record<string, unknown>): Promise<void> {
    const updated = await api.patchTopic(topicId, body);
    current.value = updated;
    await load();
  }

  return { items, current, counts, loading, error, load, loadOne, create, patch };
});
