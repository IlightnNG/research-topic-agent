/** 错误码 → 人话（spec §8）。保留原始 code，便于排查与日志对齐。 */
const MESSAGES: Record<string, string> = {
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
  const text = MESSAGES[code];
  return text ? `${text}（${code}）` : fallback;
}

export function isRetryable(code: string | undefined): boolean {
  return !["E_FEATURE_DISABLED", "E_NOT_FOUND", "E_SRC_NO_SELECTOR"].includes(code ?? "");
}
