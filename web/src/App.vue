<script setup>
import { computed, onMounted, ref } from "vue";
import { api, describeError } from "./api";

const tab = ref("topics");
const health = ref(null);
const topics = ref([]);
const metrics = ref(null);
const error = ref("");
const busy = ref("");

const form = ref({ id: "ai-agents", name: "AI Agents", scope: "llm agents and tool use" });

const runId = ref("");
const run = ref(null);
const events = ref([]);
const runReport = ref(null);
const reportMsg = ref("");

const reportRunId = ref("");
const report = ref(null);

const KNOWN_STAGES = ["intake", "scope", "retrieval", "parse", "normalize", "mapping", "analysis", "report"];
const stageState = computed(() => {
  const done = new Set();
  const current = new Set();
  for (const event of events.value) {
    if (event.type !== "phase_change") continue;
    if (event.payload?.phase === "end") done.add(event.stage);
    if (event.payload?.phase === "start") current.add(event.stage);
  }
  const stages = KNOWN_STAGES.filter((name) => done.has(name) || current.has(name));
  for (const name of done) if (!stages.includes(name)) stages.push(name);
  return stages.map((name) => ({ name, done: done.has(name) }));
});

const guardEvents = computed(() => events.value.filter((event) => event.type === "guard_trigger"));

async function withBusy(label, fn) {
  busy.value = label;
  error.value = "";
  try {
    return await fn();
  } catch (err) {
    error.value = describeError(err);
    return null;
  } finally {
    busy.value = "";
  }
}

async function refresh() {
  await withBusy("refresh", async () => {
    health.value = await api.health();
    topics.value = await api.listTopics();
    metrics.value = await api.metrics();
  });
}

async function createTopic() {
  const created = await withBusy("create", () =>
    api.createTopic({
      id: form.value.id.trim(),
      name: form.value.name.trim(),
      scope_statement: form.value.scope.trim(),
      sources: [{ source: "openalex", selector: { venue_ids: [] } }],
    }),
  );
  if (created) await refresh();
}

async function runTopic(topicId) {
  form.value.id = topicId;
  reportMsg.value = "";
  runReport.value = null;
  run.value = null;
  events.value = [];
  const result = await withBusy("run", () => api.triggerRun(topicId));
  if (!result) return;

  runId.value = result.run_id;
  reportRunId.value = result.run_id;
  await loadRun(result.run_id);
  await refresh();
  await loadReport(result.run_id, { silent: true });
}

async function loadRun(id) {
  await withBusy("load run", async () => {
    run.value = await api.getRun(id);
    const page = await api.listEvents(id, 0);
    events.value = page.items;
    reportRunId.value = id;
  });
}

async function loadReport(id, { silent = false } = {}) {
  reportMsg.value = "";
  try {
    runReport.value = await api.getRunReport(id);
    report.value = runReport.value;
    if (!silent) tab.value = "report";
  } catch (err) {
    runReport.value = null;
    reportMsg.value = describeError(err);
  }
}

function openReport(id) {
  reportRunId.value = id;
  tab.value = "report";
  loadReport(id);
}

async function chatProbe() {
  reportMsg.value = "";
  await withBusy("chat", async () => {
    const response = await fetch(`/api/topics/${form.value.id}/chat`);
    const payload = await response.json();
    reportMsg.value = `${response.status} ${payload.code} — ${payload.message}`;
  });
}

onMounted(refresh);
</script>

<template>
  <div class="app">
    <header>
      <div class="brand">
        <span class="dot"></span>
        <h1>lit-agent</h1>
        <span class="sub">literature research assistant · Phase 1</span>
      </div>
      <div class="chips">
        <span v-if="health" class="chip" :class="health.ok ? 'ok' : 'bad'">
          {{ health.ok ? "healthy" : "degraded" }} · schema {{ health.sqlite?.schema_version }}
        </span>
        <span v-if="metrics" class="chip">runs {{ metrics.runs }}</span>
        <span v-if="metrics" class="chip">events {{ metrics.events }}</span>
        <span v-if="metrics" class="chip">cost ${{ metrics.llm_cost_usd }}</span>
        <span v-if="busy" class="chip busy">{{ busy }}…</span>
      </div>
    </header>

    <div class="body">
      <nav class="side">
        <button :class="{ active: tab === 'topics' }" @click="tab = 'topics'">Topics</button>
        <button :class="{ active: tab === 'report' }" @click="tab = 'report'">Report</button>
        <button :class="{ active: tab === 'chat' }" @click="tab = 'chat'">Chat</button>
        <button class="ghost" @click="refresh">Refresh</button>
      </nav>

      <main>
        <p v-if="error" class="error">{{ error }}</p>

        <section v-if="tab === 'topics'">
          <h2>Topics</h2>
          <div class="card form">
            <input v-model="form.id" placeholder="topic id (slug)" />
            <input v-model="form.name" placeholder="name" />
            <input v-model="form.scope" class="wide" placeholder="scope statement" />
            <button class="primary" :disabled="!!busy" @click="createTopic">Create topic</button>
          </div>

          <div class="grid">
            <article v-for="item in topics" :key="item.id" class="card topic">
              <header class="topic-head">
                <strong>{{ item.id }}</strong>
                <span class="chip small">{{ item.status }}</span>
              </header>
              <p class="muted">{{ item.name }}</p>
              <p class="scope">{{ item.scope_statement }}</p>
              <button class="primary" :disabled="!!busy" @click="runTopic(item.id)">Run now</button>
            </article>
            <p v-if="!topics.length" class="empty">还没有 topic —— 用上面的表单建一个。</p>
          </div>

          <section v-if="run" class="card run">
            <header class="run-head">
              <h3>Run {{ run.id }}</h3>
              <span class="chip" :class="run.state === 'succeeded' ? 'ok' : 'bad'">{{ run.state }}</span>
              <span class="chip small">stage {{ run.stage }}</span>
              <span class="chip small">{{ events.length }} events</span>
              <span v-if="runReport" class="chip" :class="runReport.degraded ? 'warn' : 'ok'">
                {{ runReport.degraded ? "degraded report" : "report" }}
              </span>
            </header>

            <div class="stages">
              <div v-for="stage in stageState" :key="stage.name" class="stage" :class="{ done: stage.done }">
                <span class="mark">{{ stage.done ? "✓" : "•" }}</span>{{ stage.name }}
              </div>
            </div>

            <div v-if="guardEvents.length" class="notice warn">
              守卫触发 {{ guardEvents.length }} 次：
              <code v-for="event in guardEvents" :key="event.seq">{{ event.payload?.code }}</code>
              <span class="muted">（降级告警，不终止）</span>
            </div>

            <div class="actions">
              <button class="primary" :disabled="!!busy || !runReport" @click="openReport(run.id)">
                查看本轮报告
              </button>
              <button :disabled="!!busy" @click="loadRun(run.id)">刷新事件</button>
              <span v-if="reportMsg" class="error">{{ reportMsg }}</span>
            </div>

            <details v-if="runReport" class="preview" open>
              <summary>报告预览（{{ runReport.n_claims }} claims）</summary>
              <pre>{{ runReport.content_md }}</pre>
            </details>

            <h4>事件时间线</h4>
            <ol class="log">
              <li v-for="event in events" :key="event.seq" :class="event.severity">
                <span class="seq">#{{ event.seq }}</span>
                <span class="type">{{ event.type }}</span>
                <span class="stage">{{ event.stage }}</span>
                <details class="payload">
                  <summary>payload</summary>
                  <pre>{{ JSON.stringify(event.payload, null, 2) }}</pre>
                </details>
              </li>
            </ol>
          </section>
        </section>

        <section v-else-if="tab === 'report'">
          <h2>Report</h2>
          <div class="card form">
            <input v-model="reportRunId" class="wide" placeholder="run id（跑完会自动填入）" />
            <button class="primary" :disabled="!!busy" @click="loadReport(reportRunId)">Load</button>
          </div>
          <p v-if="reportMsg" class="error">{{ reportMsg }}</p>

          <article v-if="report" class="card">
            <header class="run-head">
              <h3>{{ report.title }}</h3>
              <span class="chip small">{{ report.report_id }}</span>
              <span class="chip small">{{ report.n_claims }} claims</span>
              <span v-if="report.degraded" class="chip warn">degraded</span>
            </header>
            <p class="muted">sha {{ report.content_sha }} · run {{ report.run_id }}</p>
            <pre class="report">{{ report.content_md }}</pre>
            <h4>Claims</h4>
            <table>
              <thead>
                <tr><th>#</th><th>text</th><th>support</th><th>citations</th></tr>
              </thead>
              <tbody>
                <tr v-for="(claim, index) in report.claims" :key="index">
                  <td>{{ index + 1 }}</td>
                  <td>{{ claim.text }}</td>
                  <td>
                    <span class="chip small" :class="claim.support === 'supported' ? 'ok' : 'warn'">
                      {{ claim.support }}
                    </span>
                  </td>
                  <td>{{ claim.citations.length }}</td>
                </tr>
              </tbody>
            </table>
          </article>
          <p v-else class="empty">还没有报告：先在 Topics 里 Run 一次，完成后会自动带出报告。</p>
        </section>

        <section v-else>
          <h2>Chat</h2>
          <div class="card">
            <p>Chat 在 Phase 1 未启用，后端返回 <code>501 E_FEATURE_DISABLED</code>（不是 404）。</p>
            <p class="muted">Phase 3 会接 Chat：问题 → 证据检索 → 带 citation 的回答。</p>
            <button :disabled="!!busy" @click="chatProbe">探测 /api/topics/{{ form.id }}/chat</button>
            <p v-if="reportMsg" class="notice warn">{{ reportMsg }}</p>
          </div>
        </section>
      </main>
    </div>
  </div>
</template>

<style>
:root {
  color-scheme: light dark;
  font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  --line: #8883;
  --bg-soft: #8881;
  --accent: #4f7cff;
}
* { box-sizing: border-box; }
body { margin: 0; }
h1, h2, h3, h4 { margin: 0 0 8px; }
h1 { font-size: 18px; }
h2 { font-size: 16px; margin-top: 4px; }
h3 { font-size: 15px; }
h4 { font-size: 13px; margin: 14px 0 6px; }
.app { min-height: 100vh; }
header {
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  padding: 14px 22px; border-bottom: 1px solid var(--line); flex-wrap: wrap;
}
.brand { display: flex; align-items: center; gap: 10px; }
.brand .dot { width: 10px; height: 10px; border-radius: 50%; background: var(--accent); }
.brand .sub { opacity: 0.6; font-size: 12px; }
.chips { display: flex; gap: 6px; flex-wrap: wrap; }
.chip { font-size: 12px; padding: 2px 9px; border-radius: 999px; border: 1px solid var(--line); background: var(--bg-soft); }
.chip.small { font-size: 11px; padding: 1px 7px; }
.chip.ok { color: #2f9e44; border-color: #2f9e4455; background: #2f9e4415; }
.chip.bad { color: #e03131; border-color: #e0313155; background: #e0313115; }
.chip.warn { color: #f08c00; border-color: #f08c0055; background: #f08c0015; }
.chip.busy { color: var(--accent); }
.body { display: grid; grid-template-columns: 168px 1fr; min-height: calc(100vh - 62px); }
.side { border-right: 1px solid var(--line); padding: 14px 10px; display: flex; flex-direction: column; gap: 6px; }
.side button {
  text-align: left; padding: 8px 12px; border-radius: 8px; border: 1px solid transparent;
  background: transparent; color: inherit; cursor: pointer; font-size: 13px;
}
.side button:hover { background: var(--bg-soft); }
.side button.active { background: #4f7cff18; border-color: #4f7cff55; color: var(--accent); }
.side button.ghost { opacity: 0.7; margin-top: auto; }
main { padding: 18px 22px 60px; max-width: 1080px; }
.card { border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px; margin-bottom: 14px; }
.form { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
input {
  padding: 7px 10px; border-radius: 8px; border: 1px solid var(--line);
  background: transparent; color: inherit; font-size: 13px; min-width: 140px;
}
input.wide { flex: 1 1 260px; }
button {
  padding: 7px 14px; border-radius: 8px; border: 1px solid var(--line);
  background: var(--bg-soft); color: inherit; cursor: pointer; font-size: 13px;
}
button:hover:not(:disabled) { border-color: var(--accent); }
button:disabled { opacity: 0.45; cursor: not-allowed; }
button.primary { border-color: var(--accent); color: var(--accent); background: #4f7cff12; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }
.topic { margin: 0; display: flex; flex-direction: column; gap: 8px; }
.topic-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.scope { font-size: 12.5px; opacity: 0.85; margin: 0; }
.muted { opacity: 0.65; font-size: 12.5px; margin: 4px 0; }
.empty { opacity: 0.6; font-size: 13px; }
.error { color: #e03131; font-size: 13px; }
.run-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.stages { display: flex; gap: 6px; flex-wrap: wrap; margin: 10px 0; }
.stage {
  font-size: 12px; padding: 3px 10px; border-radius: 999px;
  border: 1px dashed var(--line); opacity: 0.75;
}
.stage.done { border-style: solid; border-color: #2f9e4455; color: #2f9e44; background: #2f9e4412; opacity: 1; }
.stage .mark { margin-right: 5px; }
.notice { font-size: 13px; padding: 8px 12px; border-radius: 8px; border: 1px solid var(--line); margin: 10px 0; }
.notice.warn { border-color: #f08c0055; background: #f08c0012; }
.actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin: 12px 0; }
.log { list-style: none; padding: 0; margin: 0; max-height: 380px; overflow: auto; font-family: ui-monospace, monospace; }
.log li {
  display: grid; grid-template-columns: 52px 130px 110px 1fr; align-items: start;
  gap: 8px; padding: 5px 4px; border-bottom: 1px dashed var(--line); font-size: 12.5px;
}
.log li.warning { background: #f08c0010; }
.log li.error { background: #e0313110; }
.log .seq { color: var(--accent); }
.log .type { font-weight: 600; }
.log .stage { opacity: 0.7; }
.log .payload summary { cursor: pointer; opacity: 0.6; font-size: 11.5px; }
pre { white-space: pre-wrap; word-break: break-word; font-size: 12.5px; margin: 6px 0; }
table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
th, td { text-align: left; border-bottom: 1px solid var(--line); padding: 5px 6px; vertical-align: top; }
details.preview summary { cursor: pointer; font-size: 12.5px; opacity: 0.8; }
</style>
