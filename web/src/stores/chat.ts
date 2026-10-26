import { defineStore } from "pinia";
import { ref } from "vue";

import { describeError } from "@/api/client";
import { api } from "@/api/endpoints";
import type { ChatMessage, ChatSession } from "@/api/types";

export const useChatStore = defineStore("chat", () => {
  const sessions = ref<ChatSession[]>([]);
  const session = ref<ChatSession | null>(null);
  const messages = ref<ChatMessage[]>([]);
  const loading = ref(false);
  const error = ref("");

  let controller: AbortController | null = null;

  async function load(topicId: string): Promise<void> {
    try {
      const state = await api.getChat(topicId);
      sessions.value = state.sessions;
      session.value = state.session;
      messages.value = state.messages;
    } catch (err) {
      error.value = describeError(err);
    }
  }

  async function send(topicId: string, text: string): Promise<void> {
    const body = text.trim();
    if (!body || loading.value) return;
    loading.value = true;
    error.value = "";
    controller = new AbortController();
    const optimistic: ChatMessage = {
      id: `local-${Date.now()}`,
      role: "user",
      content: body,
      citations: [],
      trace: [],
      ts: new Date().toISOString(),
    };
    messages.value = [...messages.value, optimistic];

    try {
      const result = await api.postChat(
        topicId,
        { message: body, session_id: session.value?.id },
        controller.signal,
      );
      messages.value = [...messages.value, result.message];
      const known = sessions.value.find((item) => item.id === result.session_id);
      if (!known) {
        session.value = { id: result.session_id, topic_id: topicId, created_at: "" };
        sessions.value = [session.value, ...sessions.value];
      } else {
        session.value = known;
      }
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        error.value = "已中止本次回答";
      } else {
        error.value = describeError(err);
      }
    } finally {
      loading.value = false;
      controller = null;
    }
  }

  async function startNew(topicId: string): Promise<void> {
    try {
      const result = await api.createChatSession(topicId);
      session.value = {
        id: result.session_id,
        topic_id: topicId,
        created_at: new Date().toISOString(),
      };
      sessions.value = [session.value, ...sessions.value];
      messages.value = [];
      error.value = "";
    } catch (err) {
      error.value = describeError(err);
    }
  }

  function abort(): void {
    controller?.abort();
  }

  function reset(): void {
    sessions.value = [];
    session.value = null;
    messages.value = [];
    error.value = "";
    loading.value = false;
  }

  return { sessions, session, messages, loading, error, load, send, startNew, abort, reset };
});
