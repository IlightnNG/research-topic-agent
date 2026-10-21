import { onBeforeUnmount, ref } from "vue";

import type { RunEvent } from "@/api/types";

interface Options {
  onEvent: (event: RunEvent) => void;
  onDone?: (state: string | null) => void;
  /** 当前已收到的最大 seq（重连时用它续传，避免重复拉旧事件） */
  getSeq?: () => number;
}

/** SSE 订阅：断线自动重连（指数退避）；重连前由调用方先刷新快照（spec §3.2.1）。 */
export function useSse(runId: () => string | null, options: Options) {
  const connected = ref(false);
  let source: EventSource | null = null;
  let retry = 0;
  let closed = false;

  function stop(): void {
    closed = true;
    source?.close();
    source = null;
    connected.value = false;
  }

  function start(afterSeq: number): void {
    const id = runId();
    if (!id || closed) return;
    source?.close();
    const cursor = Math.max(afterSeq, options.getSeq?.() ?? 0);
    source = new EventSource(`/api/runs/${id}/stream?after_seq=${cursor}`);
    source.onopen = () => {
      connected.value = true;
      retry = 0;
    };
    source.addEventListener("end", (raw) => {
      const payload = JSON.parse((raw as MessageEvent).data || "{}") as { state?: string };
      connected.value = false;
      source?.close();
      options.onDone?.(payload.state ?? null);
    });
    source.addEventListener("heartbeat", () => undefined);
    source.onmessage = (raw) => {
      try {
        options.onEvent(JSON.parse(raw.data) as RunEvent);
      } catch {
        /* 忽略坏帧 */
      }
    };
    for (const type of ["phase_change", "tool_call", "llm_call", "guard_trigger", "report_written", "error"]) {
      source.addEventListener(type, (raw) => {
        try {
          options.onEvent(JSON.parse((raw as MessageEvent).data) as RunEvent);
        } catch {
          /* 忽略坏帧 */
        }
      });
    }
    source.onerror = () => {
      if (closed) return;
      connected.value = false;
      source?.close();
      retry += 1;
      const delay = Math.min(5000, 500 * retry);
      // 用最新 seq 重连（而不是首次的 afterSeq），否则会重复拉取历史事件
      window.setTimeout(() => start(options.getSeq?.() ?? afterSeq), delay);
    };
  }

  onBeforeUnmount(stop);
  return { start, stop, connected };
}
