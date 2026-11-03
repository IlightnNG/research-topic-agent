<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { NodeStatus, Run, RunTrace, TraceEvent } from '@/types'
import Button from '@/components/ui/Button.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import NodeProgress from './NodeProgress.vue'
import SectionProgress from './SectionProgress.vue'

const props = defineProps<{
  run: Run
  trace?: RunTrace
  loading?: boolean
  error?: string
  busy?: boolean
}>()

const emit = defineEmits<{ pause: []; resume: []; retrySection: [sectionId: string] }>()

interface RenderItem {
  kind: 'tool' | 'thinking' | 'result' | 'event'
  event: TraceEvent
  result?: TraceEvent
}

const scroller = ref<HTMLElement | null>(null)
const follow = ref(true)
const runEvents = computed(() => props.trace?.events.filter((event) => !event.node_id) ?? [])
const runStart = computed(() => runEvents.value.find((event) => event.type === 'run.started'))
const runEnd = computed(
  () => runEvents.value.filter((event) => event.type !== 'run.started' && event.type !== 'context.compacted'),
)
const runFailed = computed(() => runEnd.value.find((event) => event.type === 'run.failed'))
const currentId = computed(
  () => props.trace?.nodes.find((node) => node.status === 'running' || node.status === 'verifying')?.node_id,
)
const checkpoint = computed(() => props.trace?.checkpoint ?? props.run.last_checkpoint)

function tone(status: NodeStatus): 'neutral' | 'accent' | 'success' | 'warning' | 'danger' {
  if (status === 'committed') return 'success'
  if (status === 'running' || status === 'verifying') return 'accent'
  if (status === 'paused' || status === 'degraded') return 'warning'
  if (status === 'failed') return 'danger'
  return 'neutral'
}

function runTone(): 'neutral' | 'accent' | 'success' | 'warning' | 'danger' {
  if (props.run.state === 'succeeded') return 'success'
  if (props.run.state === 'running') return 'accent'
  if (props.run.state === 'paused' || props.run.state === 'pausing') return 'warning'
  if (props.run.state === 'failed') return 'danger'
  return 'neutral'
}

function time(ts: string): string {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function eventsFor(nodeId: string): TraceEvent[] {
  return props.trace?.events.filter((event) => event.node_id === nodeId) ?? []
}

function contextCount(nodeId: string): number {
  return eventsFor(nodeId).filter((event) => event.type === 'context.compacted').length
}

function renderItems(nodeId: string): RenderItem[] {
  const events = eventsFor(nodeId)
  const items: RenderItem[] = []
  for (let index = 0; index < events.length; index += 1) {
    const event = events[index]
    if (event.type === 'context.compacted') continue
    if (event.type === 'kernel.checkpoint' || event.type === 'kernel.step_started') continue
    if (event.type === 'section.written' || event.type === 'section.failed') continue
    if (event.type === 'tool.called' || event.type === 'kernel.tool_called') {
      const result = events
        .slice(index + 1)
        .find(
          (candidate) =>
            (candidate.type === 'tool.result' || candidate.type === 'kernel.tool_result') &&
            candidate.call_id === event.call_id,
        )
      items.push({ kind: 'tool', event, result })
      continue
    }
    if (event.type === 'tool.result' || event.type === 'kernel.tool_result') {
      if (items.some((item) => item.kind === 'tool' && item.event.call_id === event.call_id)) continue
      items.push({ kind: 'result', event })
      continue
    }
    if (event.type === 'thinking.summary') {
      items.push({ kind: 'thinking', event })
      continue
    }
    if (event.type === 'kernel.assistant_delta') continue
    items.push({ kind: 'event', event })
  }
  return items
}

function oneLine(value?: string, limit = 120): string {
  const text = (value || '').replace(/\s+/g, ' ').trim()
  if (!text) return ''
  return text.length > limit ? `${text.slice(0, limit)}…` : text
}

function toolLabel(result?: TraceEvent): string {
  if (!result) return 'Running'
  return result.ok ? 'Completed' : 'Failed'
}

function toolTone(result?: TraceEvent): 'accent' | 'success' | 'danger' {
  if (!result) return 'accent'
  return result.ok ? 'success' : 'danger'
}

function failedReason(event: TraceEvent): string {
  return event.error || event.reason || event.summary || 'Node failed without a reason.'
}

function onScroll(): void {
  const element = scroller.value
  if (!element) return
  follow.value = element.scrollTop + element.clientHeight >= element.scrollHeight - 24
}

function jumpToLatest(): void {
  follow.value = true
  if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
}

watch(
  () => props.trace?.events.length,
  async () => {
    if (!follow.value) return
    await nextTick()
    if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
  },
)
</script>

<template>
  <section class="trajectory">
    <header class="trajectory__head">
      <div>
        <p class="trajectory__eyebrow">Run trajectory</p>
        <h2>{{ run.focus_hint || 'General direction' }}</h2>
      </div>
      <div class="trajectory__controls">
        <StatusBadge :tone="runTone()">{{ run.state }}</StatusBadge>
        <Button v-if="run.state === 'running'" size="sm" variant="secondary" :disabled="busy" @click="emit('pause')">Pause</Button>
        <Button v-else-if="run.state === 'pausing'" size="sm" variant="secondary" disabled>Pausing…</Button>
      </div>
    </header>

    <div v-if="run.state === 'paused'" class="paused-banner">
      <div>
        <strong>Run paused</strong>
        <p v-if="checkpoint">{{ checkpoint.node_id }} · step {{ checkpoint.step }} · checkpoint saved</p>
        <p v-else>Checkpoint saved. Resume when you are ready.</p>
      </div>
      <Button size="sm" variant="primary" :disabled="busy" @click="emit('resume')">Resume</Button>
    </div>

    <div v-if="trace" class="trajectory__progress">
      <NodeProgress :nodes="trace.nodes" :current-id="currentId" />
    </div>

    <div ref="scroller" class="trajectory__scroll" @scroll="onScroll">
      <p v-if="loading" class="trajectory__state">Loading trace…</p>
      <p v-else-if="error" class="trajectory__state trajectory__state--error">{{ error }}</p>
      <p v-else-if="!trace || !trace.nodes.length" class="trajectory__state">No trace records yet.</p>

      <template v-else>
        <div v-if="runStart" class="run-start">
          <span class="run-start__dot"></span>
          <span>Run started</span>
          <time>{{ time(runStart.ts) }}</time>
        </div>

        <div class="timeline">
          <section v-for="(node, index) in trace.nodes" :key="node.node_id" class="node">
            <header class="node__head">
              <span class="node__index">{{ String(index + 1).padStart(2, '0') }}</span>
              <div class="node__title">
                <strong>{{ node.title }}</strong>
                <span class="mono">{{ node.node_id }}</span>
              </div>
              <StatusBadge :tone="tone(node.status)">{{ node.status }}</StatusBadge>
            </header>

            <p v-if="node.error" class="node-error"><span>!</span>{{ node.error }}</p>
            <p v-if="contextCount(node.node_id)" class="compaction-note">
              Context compacted {{ contextCount(node.node_id) }}× to keep the prompt within budget.
            </p>
            <SectionProgress
              v-if="node.node_id === 'report.write'"
              :events="eventsFor(node.node_id)"
              @retry="emit('retrySection', $event)"
            />

            <div v-if="renderItems(node.node_id).length" class="events">
              <div v-for="item in renderItems(node.node_id)" :key="item.event.id" class="event">
                <span class="event__time">{{ time(item.event.ts) }}</span>

                <template v-if="item.kind === 'tool'">
                  <article class="tool" :class="{ 'tool--failed': item.result && !item.result.ok }">
                    <header class="tool__head">
                      <span class="tool__icon">⚙</span>
                      <code>{{ item.event.tool }}</code>
                      <span class="tool__id">{{ item.event.call_id }}</span>
                      <span v-if="item.event.step" class="tool__id">step {{ item.event.step }}</span>
                      <StatusBadge :tone="toolTone(item.result)">{{ toolLabel(item.result) }}</StatusBadge>
                    </header>
                    <details v-if="item.event.args_preview" class="tool__io">
                      <summary>Input · {{ oneLine(item.event.args_preview) }}</summary>
                      <pre>{{ item.event.args_preview }}</pre>
                    </details>
                    <details v-if="item.result" class="tool__io" :class="{ 'tool__io--bad': !item.result.ok }">
                      <summary>Output · {{ oneLine(item.result.summary || item.result.error || (item.result.ok ? 'completed' : 'failed')) }}</summary>
                      <pre>{{ item.result.summary || item.result.error || (item.result.ok ? 'Tool completed' : 'Tool failed') }}</pre>
                    </details>
                    <p v-else class="tool__waiting">Waiting for result…</p>
                  </article>
                </template>

                <template v-else-if="item.kind === 'thinking'">
                  <details class="thinking">
                    <summary>
                      <span class="thinking__mark">✦</span>
                      <span>Thinking</span>
                      <span class="thinking__hint">{{ oneLine(item.event.text) }}</span>
                    </summary>
                    <p>{{ item.event.text }}</p>
                  </details>
                </template>

                <template v-else-if="item.kind === 'result'">
                  <div class="orphan-result" :class="{ 'orphan-result--bad': !item.event.ok }">
                    <span>{{ item.event.ok ? '✓' : '!' }}</span>
                    <span>{{ item.event.summary || item.event.error || item.event.tool }}</span>
                  </div>
                </template>

                <template v-else-if="item.event.type === 'node.failed'">
                  <div class="error-block"><strong>Node failed</strong><pre>{{ failedReason(item.event) }}</pre></div>
                </template>

                <template v-else-if="item.event.type === 'node.started'">
                  <span class="plain">Node started</span>
                </template>
                <template v-else-if="item.event.type === 'node.verifying'">
                  <span class="plain">Verifying output…</span>
                </template>
                <template v-else-if="item.event.type === 'node.committed'">
                  <span class="plain plain--good">Committed</span>
                </template>
                <template v-else-if="item.event.type === 'node.degraded'">
                  <span class="plain plain--warn">{{ failedReason(item.event) }}</span>
                </template>
                <template v-else-if="item.event.type === 'node.skipped'">
                  <span class="plain muted">Skipped</span>
                </template>
                <template v-else>
                  <span class="plain muted">{{ item.event.type }}</span>
                </template>
              </div>
            </div>

            <p v-else class="node__empty">
              {{ node.status === 'pending' ? 'Waiting for previous node.' : 'No recorded events.' }}
            </p>
          </section>

          <div v-if="runFailed" class="run-error">
            <strong>Run failed</strong>
            <pre>{{ runFailed.error || runFailed.reason || 'No failure reason recorded.' }}</pre>
          </div>

          <div v-for="event in runEnd.filter((item) => item.type !== 'run.failed')" :key="event.id" class="run-event">
            <span class="event__time">{{ time(event.ts) }}</span>
            <span>{{ event.type === 'run.finished' ? `Run ${event.state}` : event.type }}</span>
          </div>
        </div>
      </template>

      <button v-if="!follow && trace" type="button" class="jump" @click="jumpToLatest">Jump to latest</button>
    </div>
  </section>
</template>

<style scoped>
.trajectory { display: flex; flex-direction: column; min-height: 0; height: 100%; background: var(--surface); }
.trajectory__head { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); padding: 18px 20px 14px; }
.trajectory__eyebrow { margin-bottom: 3px; color: var(--text-faint); font-size: 10px; font-weight: 650; letter-spacing: 0.06em; text-transform: uppercase; }
.trajectory__head h2 { font-size: 18px; font-weight: 650; }
.trajectory__controls { display: flex; align-items: center; gap: var(--space-2); }
.trajectory__progress { padding: 0 20px 14px; }
.trajectory__scroll { position: relative; flex: 1; min-height: 0; overflow: auto; padding: 16px 20px 40px; border-top: 1px solid var(--border); }
.trajectory__state { padding: 24px 0; color: var(--text-muted); font-size: 13px; }
.trajectory__state--error { color: var(--danger); }
.run-start { display: flex; align-items: center; gap: 8px; padding: 0 0 14px; color: var(--text-muted); font-size: 11px; }
.run-start__dot { width: 7px; height: 7px; border-radius: 50%; background: var(--accent); }
.run-start time { color: var(--text-faint); font-family: var(--font-mono); font-size: 10px; }
.timeline { display: flex; flex-direction: column; gap: 18px; }
.node { border-left: 1px solid var(--border); padding-left: 16px; }
.node__head { display: flex; align-items: center; gap: 10px; }
.node__index { margin-left: -25px; display: inline-flex; align-items: center; justify-content: center; width: 18px; height: 18px; border: 1px solid var(--border); border-radius: 50%; background: var(--surface); color: var(--text-faint); font-family: var(--font-mono); font-size: 9px; }
.node__title { display: flex; flex: 1; align-items: baseline; gap: 8px; min-width: 0; }
.node__title strong { font-size: 13px; font-weight: 600; }
.node__title span { overflow: hidden; color: var(--text-faint); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
.node-error { display: flex; gap: 7px; margin-top: 8px; padding: 7px 9px; border-radius: var(--radius-sm); background: var(--danger-soft); color: var(--danger); font-size: 11px; white-space: pre-wrap; }
.compaction-note { margin-top: 8px; color: var(--text-faint); font-size: 10px; }
.events { display: flex; flex-direction: column; gap: 7px; margin-top: 10px; }
.event { display: grid; grid-template-columns: 62px minmax(0, 1fr); gap: 8px; align-items: start; }
.event__time { padding-top: 3px; color: var(--text-faint); font-family: var(--font-mono); font-size: 10px; }
.thinking { border-radius: var(--radius-sm); background: var(--surface-muted); }
.thinking summary { display: flex; align-items: center; gap: 7px; padding: 7px 10px; color: var(--text-muted); cursor: pointer; font-size: 11px; list-style: none; }
.thinking summary::-webkit-details-marker { display: none; }
.thinking__mark { color: var(--accent); font-size: 11px; }
.thinking__hint { margin-left: auto; color: var(--text-faint); font-size: 9px; text-transform: uppercase; }
.thinking[open] summary { border-bottom: 1px solid var(--border); }
.thinking p { padding: 8px 10px; color: var(--text-muted); font-size: 12px; font-style: italic; line-height: 1.55; white-space: pre-wrap; }
.tool { border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--surface); }
.tool--failed { border-color: var(--danger); }
.tool__head { display: flex; align-items: center; gap: 7px; padding: 7px 10px; }
.tool__icon { color: var(--text-muted); font-size: 11px; }
.tool__head code { color: var(--text); font-family: var(--font-mono); font-size: 11px; font-weight: 600; }
.tool__id { margin-left: auto; color: var(--text-faint); font-family: var(--font-mono); font-size: 9px; }
.tool__io {
  margin-top: 6px;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
}

.tool__io summary {
  overflow: hidden;
  cursor: pointer;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool__io pre {
  overflow-x: auto;
  margin: 6px 0 0;
  padding: 8px;
  max-height: 220px;
  border-radius: 4px;
  background: var(--surface);
  color: var(--text);
  white-space: pre-wrap;
}

.tool__io--bad summary {
  color: var(--danger);
}

.thinking__hint {
  overflow: hidden;
  max-width: 65%;
  color: var(--text-faint);
  text-transform: none;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool__args { padding: 0 10px 8px; color: var(--text-muted); font-family: var(--font-mono); font-size: 10px; white-space: pre-wrap; }
.tool__result { display: flex; align-items: center; gap: 7px; padding: 5px 9px; border-top: 1px solid var(--border); border-radius: 0 0 var(--radius-sm) var(--radius-sm); background: var(--success-soft); color: var(--success); font-size: 11px; }
.tool__result--bad { background: var(--danger-soft); color: var(--danger); }
.tool__duration { margin-left: auto; color: var(--text-faint); font-family: var(--font-mono); font-size: 9px; }
.tool__waiting { padding: 5px 9px; border-top: 1px solid var(--border); color: var(--text-faint); font-size: 10px; }
.orphan-result { display: flex; gap: 7px; padding: 5px 9px; border-radius: var(--radius-sm); background: var(--success-soft); color: var(--success); font-size: 11px; }
.orphan-result--bad { background: var(--danger-soft); color: var(--danger); }
.error-block { padding: 8px 10px; border-left: 2px solid var(--danger); background: var(--danger-soft); color: var(--danger); }
.error-block strong { font-size: 11px; }
.error-block pre { margin-top: 4px; font-size: 11px; white-space: pre-wrap; }
.plain { padding-top: 3px; color: var(--text-muted); font-size: 12px; }
.plain--good { color: var(--success); }
.plain--bad { color: var(--danger); }
.plain--warn { color: var(--warning); }
.node__empty { padding: 8px 0 0 2px; color: var(--text-faint); font-size: 11px; }
.run-error { margin-top: 4px; padding: 10px 12px; border: 1px solid var(--danger); border-radius: var(--radius-sm); background: var(--danger-soft); color: var(--danger); }
.run-error strong { font-size: 12px; }
.run-error pre { margin-top: 5px; font-family: var(--font-mono); font-size: 11px; white-space: pre-wrap; }
.run-event { display: flex; gap: 10px; color: var(--text-muted); font-size: 11px; }
.paused-banner { display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); margin: 0 20px 12px; padding: 10px 12px; border: 1px solid var(--warning); border-radius: var(--radius-sm); background: var(--warning-soft); }
.paused-banner strong { font-size: 12px; }
.paused-banner p { margin-top: 2px; color: var(--text-muted); font-size: 11px; }
.jump { position: sticky; bottom: 8px; float: right; padding: 5px 10px; border: 1px solid var(--border); border-radius: 999px; background: var(--surface); color: var(--text-muted); font-size: 11px; box-shadow: var(--shadow-sm); }
</style>
