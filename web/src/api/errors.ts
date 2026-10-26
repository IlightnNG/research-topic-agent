/** Error code -> human text (spec §8). Keep the raw code for logs/debugging. */
import { locale } from "@/i18n";

const EN: Record<string, string> = {
  E_LOCK_HELD: "This topic already has a running job; wait for it to finish",
  E_SRC_NO_SELECTOR: "This topic has no data source selector configured",
  E_SRC_AUTH: "Data source quota exhausted or API key missing",
  E_NOT_FOUND: "Resource not found (it may have been deleted)",
  E_FEATURE_DISABLED: "This feature is not available yet",
  E_BUDGET_COST: "Run budget exhausted",
  E_CONFIG_INVALID: "Invalid parameters; check your input",
  E_RUN_ABORTED: "The run was aborted",
  E_SRC_TIMEOUT: "Data source timed out; try again later",
  E_GUARD_STAGNATION: "No new progress; continuing in degraded mode",
};

const ZH: Record<string, string> = {
  E_LOCK_HELD: "该 topic 已有任务在运行，请等它结束",
  E_SRC_NO_SELECTOR: "该 topic 未配置数据源，请先在 topic 设置里配置 selector",
  E_SRC_AUTH: "数据源配额用尽或缺少 API key",
  E_NOT_FOUND: "资源不存在（可能已被删除）",
  E_FEATURE_DISABLED: "该功能尚未开放",
  E_BUDGET_COST: "本次预算已用尽",
  E_CONFIG_INVALID: "参数不合法，请检查输入",
  E_RUN_ABORTED: "本次运行已被人工中止",
  E_SRC_TIMEOUT: "数据源响应超时，可稍后重试",
  E_GUARD_STAGNATION: "连续无新增，已降级继续",
};

export function humanize(code: string | undefined, fallback: string): string {
  if (!code) return fallback;
  const table = locale.value === "zh" ? ZH : EN;
  const text = table[code];
  return text ? `${text} (${code})` : fallback;
}

export function isRetryable(code: string | undefined): boolean {
  return !["E_FEATURE_DISABLED", "E_NOT_FOUND", "E_SRC_NO_SELECTOR"].includes(code ?? "");
}
