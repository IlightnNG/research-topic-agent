import type {
  ChatMessage,
  Conversation,
  CreateRunInput,
  CreateTopicInput,
  Paper,
  Report,
  Run,
  RunTrace,
  Topic,
  TopicBrief,
  TraceEvent,
} from '@/types'

const TOPICS_KEY = 'lit-agent-topics-v1'
const RUNS_KEY = 'lit-agent-runs-v1'
const REPORTS_KEY = 'lit-agent-reports-v1'
const CONVERSATIONS_KEY = 'lit-agent-conversations-v1'
const MESSAGES_KEY = 'lit-agent-messages-v1'

const seedTopics: Topic[] = [
  {
    id: 'topic-ai-agents',
    direction: 'AI agents',
    description: 'Tool-using language agents, planning, evaluation, and multi-agent systems.',
    keywords: ['LLM agents', 'tool use', 'planning', 'multi-agent'],
    exclusions: ['robotics control'],
    constraints: ['peer reviewed', '2020+'],
    created_at: new Date(Date.now() - 86400000 * 4).toISOString(),
  },
  {
    id: 'topic-fpga',
    direction: 'FPGA acceleration',
    description: 'FPGA-based acceleration for machine learning and scientific workloads.',
    keywords: ['FPGA', 'HLS', 'accelerator', 'hardware'],
    exclusions: ['ASIC-only'],
    created_at: new Date(Date.now() - 86400000 * 3).toISOString(),
  },
  {
    id: 'topic-rag',
    direction: 'Scientific RAG',
    description: 'Retrieval-augmented generation for scientific literature and citation quality.',
    keywords: ['retrieval', 'citation', 'scientific writing'],
    created_at: new Date(Date.now() - 86400000 * 2).toISOString(),
  },
]

const seedPapers: Paper[] = [
  {
    id: 'paper-p1',
    title: 'Tool-Augmented Language Agents for Literature Review',
    authors: ['M. Chen', 'A. Rivera'],
    year: 2025,
    venue: 'ACL',
    abstract:
      'We study tool-augmented language agents that retrieve papers, extract claims, and assemble literature reviews. Across three benchmarks, agents with explicit retrieval and verification tools produce reviews with more supported claims than single-pass prompting.',
    source_url: 'https://example.org/p1',
  },
  {
    id: 'paper-p2',
    title: 'Citation-Centric Evaluation of Scientific Summaries',
    authors: ['S. Patel', 'J. Kim'],
    year: 2025,
    venue: 'EMNLP',
    abstract:
      'We introduce a citation-centric evaluation for scientific summaries. Each factual sentence must cite a claim extracted from a source paper. Results show that retrieval quality dominates generation quality on this benchmark.',
    source_url: 'https://example.org/p2',
  },
  {
    id: 'paper-p3',
    title: 'Planning Long-Form Reports with Section-Level Agents',
    authors: ['L. Novak'],
    year: 2024,
    venue: 'NAACL',
    abstract:
      'We compare monolithic report generation with section-level planning. A planner first chooses required and optional sections, then writers draft each section against a shared evidence table. Section-level planning improves coverage and reduces repeated claims, but increases orchestration cost.',
    source_url: 'https://example.org/p3',
  },
  {
    id: 'paper-p4',
    title: 'HLS-Based FPGA Acceleration for Transformer Inference',
    authors: ['R. Singh', 'T. Watanabe'],
    year: 2024,
    venue: 'FPGA',
    abstract:
      'We present an HLS-based FPGA accelerator for transformer inference. The design overlaps attention and feed-forward stages and reduces end-to-end latency compared with a GPU baseline under a fixed power budget.',
    source_url: 'https://example.org/p4',
  },
]

const seedReports: Report[] = [
  {
    id: 'report-ai-1',
    run_id: 'run-ai-1',
    title: 'AI Agents: A Scoped Review',
    state: 'complete',
    word_count: 2840,
    sections: [
      {
        section_id: 'overview',
        kind: 'overview',
        title: 'At a Glance',
        body:
          'Recent work on AI agents focuses on tool use, evidence grounding, and report planning [C1]. Citation-centric evaluation is emerging as a way to measure whether generated claims are actually supported [C2]. Section-level planning is a separate line of work that trades orchestration cost for coverage [C3].',
        paper_links: [
          { token: 'C1', paper_id: 'paper-p1', label: 'C1' },
          { token: 'C2', paper_id: 'paper-p2', label: 'C2' },
          { token: 'C3', paper_id: 'paper-p3', label: 'C3' },
        ],
      },
      {
        section_id: 'paper_analysis_001',
        kind: 'paper_analysis',
        title: 'Papers 1-3',
        body:
          'P1 studies tool-augmented agents that retrieve papers, extract claims, and assemble reviews [C1]. P2 introduces citation-centric evaluation and reports that retrieval quality dominates generation quality [C2]. P3 compares monolithic generation with section-level planning and finds coverage gains at higher orchestration cost [C3].',
        paper_links: [
          { token: 'C1', paper_id: 'paper-p1', label: 'C1' },
          { token: 'C2', paper_id: 'paper-p2', label: 'C2' },
          { token: 'C3', paper_id: 'paper-p3', label: 'C3' },
        ],
      },
      {
        section_id: 'synthesis',
        kind: 'synthesis',
        title: 'Cross-Paper Synthesis',
        body:
          'The papers converge on a simple claim: evidence quality and explicit verification matter more than prose fluency [C1][C2]. They diverge on where structure should live: in retrieval and verification [C1], in evaluation [C2], or in section planning [C3].',
        paper_links: [
          { token: 'C1', paper_id: 'paper-p1', label: 'C1' },
          { token: 'C2', paper_id: 'paper-p2', label: 'C2' },
          { token: 'C3', paper_id: 'paper-p3', label: 'C3' },
        ],
      },
      {
        section_id: 'paper_index',
        kind: 'paper_index',
        title: 'Paper Index',
        body:
          'P1 Tool-Augmented Language Agents for Literature Review\nP2 Citation-Centric Evaluation of Scientific Summaries\nP3 Planning Long-Form Reports with Section-Level Agents',
        paper_links: [
          { token: 'P1', paper_id: 'paper-p1', label: 'P1' },
          { token: 'P2', paper_id: 'paper-p2', label: 'P2' },
          { token: 'P3', paper_id: 'paper-p3', label: 'P3' },
        ],
      },
    ],
  },
  {
    id: 'report-fpga-1',
    run_id: 'run-fpga-1',
    title: 'FPGA Acceleration: A Scoped Review',
    state: 'complete',
    word_count: 2460,
    sections: [
      {
        section_id: 'overview',
        kind: 'overview',
        title: 'At a Glance',
        body:
          'FPGA acceleration work focuses on latency and power under a fixed budget [C1]. HLS makes accelerator design more accessible but shifts complexity into scheduling and memory management [C1].',
        paper_links: [{ token: 'C1', paper_id: 'paper-p4', label: 'C1' }],
      },
      {
        section_id: 'paper_analysis_001',
        kind: 'paper_analysis',
        title: 'Paper Analysis',
        body:
          'P4 presents an HLS-based transformer accelerator that overlaps attention and feed-forward stages [C1]. The result is lower end-to-end latency than a GPU baseline under the same power budget [C1].',
        paper_links: [{ token: 'C1', paper_id: 'paper-p4', label: 'C1' }],
      },
    ],
  },
]

const seedConversations: Conversation[] = [
  {
    id: 'conv-ai-1',
    topic_id: 'topic-ai-agents',
    title: 'Agent evaluation questions',
    created_at: new Date(Date.now() - 3600000).toISOString(),
    updated_at: new Date(Date.now() - 1200000).toISOString(),
    message_count: 2,
  },
  {
    id: 'conv-ai-2',
    topic_id: 'topic-ai-agents',
    title: 'Report scope',
    created_at: new Date(Date.now() - 86400000).toISOString(),
    updated_at: new Date(Date.now() - 82800000).toISOString(),
    message_count: 2,
  },
  {
    id: 'conv-fpga-1',
    topic_id: 'topic-fpga',
    title: 'HLS latency trade-offs',
    created_at: new Date(Date.now() - 7200000).toISOString(),
    updated_at: new Date(Date.now() - 3600000).toISOString(),
    message_count: 2,
  },
]

const seedMessages: ChatMessage[] = [
  {
    id: 'msg-ai-1-u',
    conversation_id: 'conv-ai-1',
    role: 'user',
    content: 'How should I evaluate multi-agent systems?',
    created_at: new Date(Date.now() - 1800000).toISOString(),
    state: 'done',
  },
  {
    id: 'msg-ai-1-a',
    conversation_id: 'conv-ai-1',
    role: 'assistant',
    content:
      'Start with task success and evidence grounding. Then separate coordination failures from individual agent failures, and report latency and token cost alongside quality. The report workspace can turn those claims into a scoped review.',
    created_at: new Date(Date.now() - 1200000).toISOString(),
    state: 'done',
  },
  {
    id: 'msg-ai-2-u',
    conversation_id: 'conv-ai-2',
    role: 'user',
    content: 'What belongs in an AI agents topic?',
    created_at: new Date(Date.now() - 84000000).toISOString(),
    state: 'done',
  },
  {
    id: 'msg-ai-2-a',
    conversation_id: 'conv-ai-2',
    role: 'assistant',
    content:
      'Keep it to tool-using language agents, planning, and evaluation. Exclude robotics control and low-level hardware. Use constraints such as peer-reviewed and 2020+.',
    created_at: new Date(Date.now() - 82800000).toISOString(),
    state: 'done',
  },
  {
    id: 'msg-fpga-1-u',
    conversation_id: 'conv-fpga-1',
    role: 'user',
    content: 'What should I compare in an FPGA accelerator paper?',
    created_at: new Date(Date.now() - 7200000).toISOString(),
    state: 'done',
  },
  {
    id: 'msg-fpga-1-a',
    conversation_id: 'conv-fpga-1',
    role: 'assistant',
    content:
      'Compare latency, throughput, power, and resource utilization. Report the baseline and the workload shape; an accelerator result without those is hard to interpret.',
    created_at: new Date(Date.now() - 3600000).toISOString(),
    state: 'done',
  },
]

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms)
    signal?.addEventListener('abort', () => {
      clearTimeout(timer)
      reject(new DOMException('Aborted', 'AbortError'))
    }, { once: true })
  })
}

const seedRuns: Run[] = [
  {
    id: 'run-ai-1',
    topic_id: 'topic-ai-agents',
    state: 'succeeded',
    language: 'en',
    focus_hint: 'multi-agent evaluation',
    report_id: 'report-ai-1',
    created_at: new Date(Date.now() - 86400000).toISOString(),
    started_at: new Date(Date.now() - 86400000).toISOString(),
    finished_at: new Date(Date.now() - 86400000 + 240000).toISOString(),
    last_checkpoint: {
      node_id: 'report.generate',
      step: 7,
      created_at: new Date(Date.now() - 86400000 + 240000).toISOString(),
    },
  },
  {
    id: 'run-ai-2',
    topic_id: 'topic-ai-agents',
    state: 'running',
    language: 'en',
    created_at: new Date(Date.now() - 600000).toISOString(),
    started_at: new Date(Date.now() - 600000).toISOString(),
    last_checkpoint: {
      node_id: 'evidence.extract',
      step: 3,
      created_at: new Date(Date.now() - 60000).toISOString(),
    },
  },
  {
    id: 'run-ai-failed',
    topic_id: 'topic-ai-agents',
    state: 'failed',
    language: 'en',
    focus_hint: 'failed example',
    created_at: new Date(Date.now() - 1800000).toISOString(),
    started_at: new Date(Date.now() - 1800000).toISOString(),
    finished_at: new Date(Date.now() - 1740000).toISOString(),
  },
  {
    id: 'run-fpga-1',
    topic_id: 'topic-fpga',
    state: 'succeeded',
    language: 'en',
    focus_hint: 'HLS-based accelerators',
    report_id: 'report-fpga-1',
    created_at: new Date(Date.now() - 86400000 * 2).toISOString(),
    started_at: new Date(Date.now() - 86400000 * 2).toISOString(),
    finished_at: new Date(Date.now() - 86400000 * 2 + 180000).toISOString(),
  },
]

function read<T>(key: string, seed: T[]): T[] {
  const raw = localStorage.getItem(key)
  if (!raw) {
    localStorage.setItem(key, JSON.stringify(seed))
    return structuredClone(seed)
  }
  try {
    return JSON.parse(raw) as T[]
  } catch {
    localStorage.setItem(key, JSON.stringify(seed))
    return structuredClone(seed)
  }
}

function write<T>(key: string, value: T[]): void {
  localStorage.setItem(key, JSON.stringify(value))
}

function newId(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`
}

function delay<T>(value: T, ms = 120): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms))
}

function makeBrief(topic: Topic): TopicBrief {
  const scope = topic.description?.trim() || topic.direction
  return {
    topic_id: topic.id,
    normalized_title: `${topic.direction}: scoped research brief`,
    scope_statement: `${scope} Stay within ${topic.direction}.`,
    include_criteria: [
      `Directly relevant to ${topic.direction}`,
      ...(topic.keywords ?? []).map((keyword) => `Mentions ${keyword}`),
      ...(topic.constraints ?? []),
    ],
    exclude_criteria: topic.exclusions ?? [],
    search_queries: [
      `${topic.direction} review`,
      `${topic.direction} ${topic.keywords?.[0] ?? 'methods'}`,
      `${topic.direction} evaluation`,
    ],
    language: 'en',
    created_at: new Date().toISOString(),
  }
}

function event(
  runId: string,
  index: number,
  type: TraceEvent['type'],
  nodeId: string | undefined,
  extra: Partial<TraceEvent> = {},
): TraceEvent {
  return {
    id: `${runId}-evt-${index}`,
    type,
    node_id: nodeId,
    ts: new Date(Date.now() - (18 - index) * 30000).toISOString(),
    ...extra,
  }
}

function seedTrace(runId: string): RunTrace {
  if (runId === 'run-ai-1') {
    const events = [
      event(runId, 0, 'run.started', undefined),
      event(runId, 1, 'node.started', 'source.collect'),
      event(runId, 2, 'thinking.summary', 'source.collect', {
        text: 'The topic is AI agents. I will search for tool-using agents, planning, and multi-agent evaluation.',
      }),
      event(runId, 3, 'tool.called', 'source.collect', {
        tool: 'source.search',
        call_id: 'call_1',
        args_preview: 'query="AI agents", limit=40',
      }),
      event(runId, 4, 'tool.result', 'source.collect', {
        tool: 'source.search',
        call_id: 'call_1',
        ok: true,
        summary: '40 papers returned',
        duration_ms: 1820,
      }),
      event(runId, 5, 'node.committed', 'source.collect'),
      event(runId, 6, 'node.started', 'evidence.extract'),
      event(runId, 7, 'thinking.summary', 'evidence.extract', {
        text: 'I will keep only claims with exact quotes and drop author lists and references.',
      }),
      event(runId, 8, 'tool.called', 'evidence.extract', {
        tool: 'claims.extract',
        call_id: 'call_2',
        args_preview: 'paper_id=P07, limit=2',
      }),
      event(runId, 9, 'tool.result', 'evidence.extract', {
        tool: 'claims.extract',
        call_id: 'call_2',
        ok: true,
        summary: '2 claims, both quoted',
        duration_ms: 940,
      }),
      event(runId, 10, 'node.verifying', 'evidence.extract'),
      event(runId, 11, 'node.committed', 'evidence.extract'),
      event(runId, 12, 'node.started', 'report.generate'),
      event(runId, 13, 'thinking.summary', 'report.generate', {
        text: 'The evidence is sufficient for an overview, per-paper analysis, synthesis, and an index.',
      }),
      event(runId, 14, 'tool.called', 'report.generate', {
        tool: 'report.plan',
        call_id: 'call_3',
        args_preview: 'sections=overview,paper_analysis,synthesis,paper_index',
      }),
      event(runId, 15, 'tool.result', 'report.generate', {
        tool: 'report.plan',
        call_id: 'call_3',
        ok: true,
        summary: '4 sections planned',
        duration_ms: 120,
      }),
      event(runId, 16, 'node.verifying', 'report.generate'),
      event(runId, 17, 'node.committed', 'report.generate'),
      event(runId, 18, 'run.finished', undefined, { state: 'succeeded' }),
    ]
    return {
      run_id: runId,
      nodes: [
        { node_id: 'source.collect', title: 'Source collect', status: 'committed' },
        { node_id: 'evidence.extract', title: 'Evidence extract', status: 'committed' },
        { node_id: 'report.generate', title: 'Report generate', status: 'committed' },
      ],
      events,
    }
  }

  if (runId === 'run-ai-2') {
    const events = [
      event(runId, 0, 'run.started', undefined),
      event(runId, 1, 'node.started', 'source.collect'),
      event(runId, 2, 'thinking.summary', 'source.collect', {
        text: 'The focus is the general topic direction. I will collect a balanced candidate set.',
      }),
      event(runId, 3, 'tool.called', 'source.collect', {
        tool: 'source.search',
        call_id: 'call_1',
        args_preview: 'query="AI agents", limit=100',
      }),
      event(runId, 4, 'tool.result', 'source.collect', {
        tool: 'source.search',
        call_id: 'call_1',
        ok: true,
        summary: '100 papers returned',
        duration_ms: 2040,
      }),
      event(runId, 5, 'node.committed', 'source.collect'),
      event(runId, 6, 'node.started', 'evidence.extract'),
      event(runId, 7, 'thinking.summary', 'evidence.extract', {
        text: 'I am extracting claim candidates now. This is a long step.',
      }),
    ]
    return {
      run_id: runId,
      nodes: [
        { node_id: 'source.collect', title: 'Source collect', status: 'committed' },
        { node_id: 'evidence.extract', title: 'Evidence extract', status: 'running' },
        { node_id: 'report.generate', title: 'Report generate', status: 'pending' },
      ],
      events,
      checkpoint: { node_id: 'evidence.extract', step: 3, created_at: new Date().toISOString() },
    }
  }

  if (runId === 'run-fpga-1') {
    const events = [
      event(runId, 0, 'run.started', undefined),
      event(runId, 1, 'node.started', 'source.collect'),
      event(runId, 2, 'tool.called', 'source.collect', {
        tool: 'source.search',
        call_id: 'call_1',
        args_preview: 'query="FPGA acceleration", limit=40',
      }),
      event(runId, 3, 'tool.result', 'source.collect', {
        tool: 'source.search',
        call_id: 'call_1',
        ok: true,
        summary: '40 papers returned',
        duration_ms: 1690,
      }),
      event(runId, 4, 'node.committed', 'source.collect'),
      event(runId, 5, 'node.started', 'evidence.extract'),
      event(runId, 6, 'node.committed', 'evidence.extract'),
      event(runId, 7, 'node.started', 'report.generate'),
      event(runId, 8, 'node.committed', 'report.generate'),
      event(runId, 9, 'run.finished', undefined, { state: 'succeeded' }),
    ]
    return {
      run_id: runId,
      nodes: [
        { node_id: 'source.collect', title: 'Source collect', status: 'committed' },
        { node_id: 'evidence.extract', title: 'Evidence extract', status: 'committed' },
        { node_id: 'report.generate', title: 'Report generate', status: 'committed' },
      ],
      events,
    }
  }

  if (runId === 'run-ai-failed') {
    return {
      run_id: runId,
      nodes: [
        { node_id: 'report.generate', title: 'Report generate', status: 'failed', error: 'Verifier rejected the report: 0 claims with exact quotes.' },
      ],
      events: [
        event(runId, 0, 'run.started', undefined),
        event(runId, 1, 'node.started', 'report.generate'),
        event(runId, 2, 'thinking.summary', 'report.generate', {
          text: 'I will generate the report from the current corpus.',
        }),
        event(runId, 3, 'tool.called', 'report.generate', {
          tool: 'report.write_section',
          call_id: 'call_failed',
          args_preview: 'section=overview',
        }),
        event(runId, 4, 'tool.result', 'report.generate', {
          tool: 'report.write_section',
          call_id: 'call_failed',
          ok: false,
          error: 'E_TOOL_SCHEMA',
          summary: 'claims must be a non-empty array',
        }),
        event(runId, 5, 'node.failed', 'report.generate', {
          error: 'Verifier rejected the report: 0 claims with exact quotes.',
        }),
        event(runId, 6, 'run.failed', undefined, {
          error: 'Verifier rejected the report: 0 claims with exact quotes.',
        }),
      ],
    }
  }

  return {
    run_id: runId,
    nodes: [
      { node_id: 'source.collect', title: 'Source collect', status: 'running' },
      { node_id: 'evidence.extract', title: 'Evidence extract', status: 'pending' },
      { node_id: 'report.generate', title: 'Report generate', status: 'pending' },
    ],
    events: [event(runId, 1, 'node.started', 'source.collect')],
  }
}

export const mockApi = {
  async listTopics(): Promise<Topic[]> {
    return delay(read<Topic>(TOPICS_KEY, seedTopics))
  },

  async getTopic(id: string): Promise<Topic | undefined> {
    return delay(read<Topic>(TOPICS_KEY, seedTopics).find((topic) => topic.id === id))
  },

  async createTopic(input: CreateTopicInput): Promise<Topic> {
    const topics = read<Topic>(TOPICS_KEY, seedTopics)
    const topic: Topic = {
      id: newId('topic'),
      direction: input.direction.trim(),
      description: input.description?.trim() || undefined,
      keywords: input.keywords,
      exclusions: input.exclusions,
      constraints: input.constraints,
      created_at: new Date().toISOString(),
    }
    topics.unshift(topic)
    write(TOPICS_KEY, topics)
    return delay(topic)
  },

  async getTopicBrief(topicId: string): Promise<TopicBrief | undefined> {
    const topic = read<Topic>(TOPICS_KEY, seedTopics).find((item) => item.id === topicId)
    return delay(topic ? makeBrief(topic) : undefined)
  },

  async listRuns(topicId: string): Promise<Run[]> {
    return delay(
      read<Run>(RUNS_KEY, seedRuns)
        .filter((run) => run.topic_id === topicId)
        .sort((a, b) => b.created_at.localeCompare(a.created_at)),
    )
  },

  async createRun(topicId: string, input: CreateRunInput): Promise<Run> {
    const runs = read<Run>(RUNS_KEY, seedRuns)
    const run: Run = {
      id: newId('run'),
      topic_id: topicId,
      state: 'running',
      language: input.language,
      focus_hint: input.focus_hint?.trim() || undefined,
      created_at: new Date().toISOString(),
      started_at: new Date().toISOString(),
      last_checkpoint: { node_id: 'source.collect', step: 0, created_at: new Date().toISOString() },
    }
    runs.unshift(run)
    write(RUNS_KEY, runs)
    return delay(run)
  },

  async pauseRun(runId: string): Promise<Run> {
    const runs = read<Run>(RUNS_KEY, seedRuns)
    const run = runs.find((item) => item.id === runId)
    if (!run) throw new Error('Run not found')
    run.state = 'paused'
    run.last_checkpoint = {
      node_id: run.last_checkpoint?.node_id ?? 'source.collect',
      step: run.last_checkpoint?.step ?? 1,
      created_at: new Date().toISOString(),
    }
    write(RUNS_KEY, runs)
    return delay(run)
  },

  async resumeRun(runId: string): Promise<Run> {
    const runs = read<Run>(RUNS_KEY, seedRuns)
    const run = runs.find((item) => item.id === runId)
    if (!run) throw new Error('Run not found')
    run.state = 'running'
    write(RUNS_KEY, runs)
    return delay(run)
  },

  async deleteRun(runId: string): Promise<void> {
    write(
      RUNS_KEY,
      read<Run>(RUNS_KEY, seedRuns).filter((run) => run.id !== runId),
    )
    write(
      REPORTS_KEY,
      read<Report>(REPORTS_KEY, seedReports).filter((report) => report.run_id !== runId),
    )
    return delay(undefined)
  },

  async getTrace(runId: string): Promise<RunTrace> {
    const runs = read<Run>(RUNS_KEY, seedRuns)
    const run = runs.find((item) => item.id === runId)
    const trace = seedTrace(runId)
    if (run?.state === 'paused') {
      for (const node of trace.nodes) {
        if (node.status === 'running') node.status = 'paused'
      }
      trace.events.push(
        event(runId, trace.events.length + 1, 'run.paused', undefined, {
          checkpoint: run.last_checkpoint,
        }),
      )
    }
    if (run?.last_checkpoint) trace.checkpoint = run.last_checkpoint
    return delay(trace)
  },

  async getReport(runId: string): Promise<Report | undefined> {
    return delay(read<Report>(REPORTS_KEY, seedReports).find((report) => report.run_id === runId))
  },

  async getPaper(paperId: string): Promise<Paper | undefined> {
    return delay(seedPapers.find((paper) => paper.id === paperId))
  },

  async listConversations(topicId: string): Promise<Conversation[]> {
    return delay(
      read<Conversation>(CONVERSATIONS_KEY, seedConversations)
        .filter((conversation) => conversation.topic_id === topicId)
        .sort((a, b) => b.updated_at.localeCompare(a.updated_at)),
    )
  },

  async createConversation(topicId: string): Promise<Conversation> {
    const conversations = read<Conversation>(CONVERSATIONS_KEY, seedConversations)
    const conversation: Conversation = {
      id: newId('conv'),
      topic_id: topicId,
      title: 'New conversation',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      message_count: 0,
    }
    conversations.unshift(conversation)
    write(CONVERSATIONS_KEY, conversations)
    return delay(conversation)
  },

  async deleteConversation(conversationId: string): Promise<void> {
    write(
      CONVERSATIONS_KEY,
      read<Conversation>(CONVERSATIONS_KEY, seedConversations).filter(
        (conversation) => conversation.id !== conversationId,
      ),
    )
    write(
      MESSAGES_KEY,
      read<ChatMessage>(MESSAGES_KEY, seedMessages).filter(
        (message) => message.conversation_id !== conversationId,
      ),
    )
    return delay(undefined)
  },

  async getMessages(conversationId: string): Promise<ChatMessage[]> {
    return delay(
      read<ChatMessage>(MESSAGES_KEY, seedMessages)
        .filter((message) => message.conversation_id === conversationId)
        .sort((a, b) => a.created_at.localeCompare(b.created_at)),
    )
  },

  async sendMessage(
    conversationId: string,
    content: string,
    onChunk: (chunk: string) => void,
    signal?: AbortSignal,
  ): Promise<ChatMessage> {
    const messages = read<ChatMessage>(MESSAGES_KEY, seedMessages)
    const conversations = read<Conversation>(CONVERSATIONS_KEY, seedConversations)
    const conversation = conversations.find((item) => item.id === conversationId)
    if (!conversation) throw new Error('Conversation not found')
    const user: ChatMessage = {
      id: newId('msg'),
      conversation_id: conversationId,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
      state: 'done',
    }
    messages.push(user)
    const reply =
      'Here is a scoped answer. The topic brief keeps the discussion inside its direction. ' +
      'Use the Report workspace when you want a traceable review with citations; use this chat for quick orientation and follow-up questions.'
    const assistant: ChatMessage = {
      id: newId('msg'),
      conversation_id: conversationId,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
      state: 'streaming',
    }
    for (const chunk of reply.match(/.{1,18}/g) ?? []) {
      await sleep(45, signal)
      assistant.content += chunk
      onChunk(chunk)
    }
    assistant.state = 'done'
    messages.push(assistant)
    conversation.message_count = messages.filter((message) => message.conversation_id === conversationId).length
    conversation.updated_at = new Date().toISOString()
    if (conversation.title === 'New conversation') {
      conversation.title = content.slice(0, 44)
    }
    write(MESSAGES_KEY, messages)
    write(CONVERSATIONS_KEY, conversations)
    return delay(assistant, 0)
  },
}
