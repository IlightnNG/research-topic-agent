import { ref } from "vue";

export type Locale = "en" | "zh";

// UI is English by default. A language switch will live in Settings later.
export const locale = ref<Locale>("en");

export function setLocale(next: Locale): void {
  locale.value = next;
  if (typeof localStorage !== "undefined") localStorage.setItem("lit-locale", next);
}

const messages: Record<Locale, Record<string, string>> = {
  en: {
    "chat.conversations": "Conversations",
    "chat.new": "New chat",
    "chat.emptyTitle": "No conversations yet",
    "chat.emptyHint": "Ask a question to start a new conversation.",
    "chat.subtitle": "Answers must cite evidence; without a hit the assistant refuses.",
    "chat.placeholder": "Ask about this topic, Enter to send",
    "chat.send": "Send",
    "chat.stop": "Stop",
    "chat.toolTrace": "Tool trace",
    "chat.noMessages": "Ask a question about this topic, e.g. “How does tool use affect agents?”",
    "chat.no_evidence": "I can't answer from this topic's evidence: no citable snippets matched.",
    "chat.unsupported": "The matched snippets are insufficient to verify an answer.",
    "stage.intake": "Intake",
    "stage.scope": "Scope",
    "stage.retrieval": "Retrieval",
    "stage.parse": "Parse",
    "stage.normalize": "Normalize",
    "stage.mapping": "Mapping",
    "stage.analysis": "Analysis",
    "stage.critique": "Critique",
    "stage.report": "Report",
    "stage.evaluate": "Evaluate",
    "run.slowest": "Slowest",
    "common.retry": "Retry",
    "common.details": "Details",
    "common.abort": "Abort",
    "common.report": "Report",
    "common.trajectory": "Trajectory",
    "common.topics": "Topics",
  },
  zh: {
    "chat.conversations": "会话",
    "chat.new": "新建对话",
    "chat.emptyTitle": "暂无对话",
    "chat.emptyHint": "提一个问题即可开始新会话。",
    "chat.subtitle": "回答必须带引用；没有命中证据会明确拒答。",
    "chat.placeholder": "输入问题，回车发送",
    "chat.send": "发送",
    "chat.stop": "中止",
    "chat.toolTrace": "工具轨迹",
    "chat.noMessages": "问一个关于本 topic 的问题，例如「工具使用对 agent 有什么影响？」",
    "chat.no_evidence": "无法从本 topic 的证据回答这个问题（没有命中可引用的片段）。",
    "chat.unsupported": "命中的片段不足以验证回答，已拒答。",
    "stage.intake": "接入",
    "stage.scope": "界定",
    "stage.retrieval": "检索",
    "stage.parse": "解析",
    "stage.normalize": "归一",
    "stage.mapping": "映射",
    "stage.analysis": "分析",
    "stage.critique": "自查",
    "stage.report": "成文",
    "stage.evaluate": "评测",
    "run.slowest": "最慢",
    "common.retry": "重试",
    "common.details": "详情",
    "common.abort": "中止",
    "common.report": "报告",
    "common.trajectory": "轨迹",
    "common.topics": "Topics",
  },
};

export function t(key: string): string {
  return messages[locale.value][key] ?? messages.en[key] ?? key;
}
