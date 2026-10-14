# Problem 页（Slide 8–13）中英对照 + 设计动机

> 用途：台上照读/台下应答的对照稿。**英文与 PPT 上的文字逐字一致**（标题、hero、Problem、Methods、Verify、脚注、takeaway）；
> 中文是对应翻译，其中"标题下注解"一行本身就是 PPT 上已渲染的那行灰字。
> 每页末尾的 **Why these solutions are needed** 说明"不做会怎样"——这是导师追问"为什么要这么设计"时的答法。
> 数字口径与 `group-meeting-outline.md`、`phase0-decision-gate.md` 一致。

---

## Slide 8 · Problem 1 — Anti-drift

| English (as on the slide) | 中文对应 |
|---|---|
| PROBLEM 1 · ANTI-DRIFT | 问题 1 · 防走偏 |
| **How we keep a weekly run on topic** | **如何让每周长跑始终不跑题** |
| 如何防止 agent 走偏 *(标题下灰字注解)* | （即为本页中文注解） |
| **Hero:** Scope Anchor and stage contracts keep runs on topic | **核心结论：** Scope Anchor + 阶段契约让长跑不跑题 |
| 15/15 drifts caught · 0 false alarms | 15/15 次注入的漂移全部被抓到 · 正常 run 0 误报 |
| block 0.0777 · warn 0.0867 | 阻断阈值 0.0777 · 告警阈值 0.0867 |
| **Problem** | **问题** |
| early drift is amplified downstream, and "zero drift" cannot be promised | 早期一步跑偏会被后续放大，而且"零漂移"无法承诺 |
| detection must be bounded, detectable, reversible, measurable — not prompt-level hope | 检测必须有界、可检出、可回退、可量化——不能靠提示词里的"请小心" |
| **Methods — six levers, all deterministic** | **办法：六个杠杆，全部是确定性的** |
| Scope Anchor — statement, boundaries, counter-examples | 范围锚点：目标陈述 + 边界 + 反例说明 |
| Stage contracts — schema per stage, no stage skipping | 阶段契约：每个阶段有输入/输出 schema，不允许跳阶段 |
| Role split + cross-vendor critic — critic never writes | 角色分离 + 异源审稿：评审者只审不写 |
| Evidence-first — every claim carries a resolvable citation | 证据优先：每条断言都必须带可回查引用 |
| Hard limits in code — whitelist, window, fingerprints | 硬约束写在代码里：源白名单、时间窗、去重指纹 |
| Cross-week anchoring — persist state, diff, flag slow drift | 跨周锚定：持久化状态、与上期 diff、标注慢性漂移 |
| **Verify** — fault injection + guard-on/off ablation | **验证方式：** 故障注入 + 守卫开/关消融 |
| off-topic results injected into a sandbox copy | 把离题结果注入到测试副本里 |
| *(footnote)* keyword-string scope overlapped: · min(on) 0.0885 > max(off) 0.0670 · block 0.0777 · warn 0.0867 | *（脚注）* 关键词式 scope 表示下正负分布重叠；改用种子语料质心后 min(正)=0.0885 > max(负)=0.0670，据此定阈值 0.0777/0.0867 |
| **Takeaway:** Detected, reversible, measured | **收口：** 可检出、可回退、可量化 |

**Why these solutions are needed（为什么需要这些办法）**

1. **周更是"无人值守长链"**：一次 run 跨小时（检索→建图→分析→报告），早期一步出错会被后续步骤放大（漂移→幻觉→错误报告级联）。所以必须有"锚"（Scope Anchor）和阶段契约，把偏差挡在源头，而不是靠最后人工发现。
2. **模型本身非确定、不可信"自觉"**：提示词层面的"请保持主题一致"无法判定对错，也无法单测。因此把检测做成**节点前后的守卫函数**——可单测、可注入、可统计检出率。
3. **阈值不能拍**：初值 0.6/0.45 来自 embedding 口径，实测发现关键词式 scope 表示下正负分布重叠（**任何阈值都不可分**，正常 run 全误报）。换成种子语料质心表示后分布可分，才得到 0.0777/0.0867，并做到 TPR 1.0 / FPR 0——**换表示比调数字更根本**。
4. **"零漂移"是不诚实的承诺**：能承诺的只有"有界 + 可检出 + 可回退 + 可量化"，这也是本页 hero 想传达的口径。

---

## Slide 9 · Problem 2 — Loops and stagnation

| English (as on the slide) | 中文对应 |
|---|---|
| PROBLEM 2 · LOOPS AND STAGNATION | 问题 2 · 死循环与停滞 |
| **How it notices it is going in circles** | **它如何察觉自己在原地打转** |
| 死循环与停滞：检出与处置 *(标题下灰字注解)* | （即为本页中文注解） |
| **Hero:** Bounded retries stop a loop after one replan | **核心结论：** 有限次回退：一次重规划后就强制停止 |
| 3/3 loops ended within six steps | 3/3 次循环注入都在 6 步内终止 |
| 0 false positives · degrade then abort | 0 误报；停滞场景走"降档 → 终止" |
| **Problem** | **问题** |
| the same query re-issued, zero new facts, cost rising | 同一查询反复发出、没有任何新事实，成本却持续上升 |
| the run pays for motion without progress | 这个 run 在为"动作"付费，却没有产出 |
| **Methods — four detectors plus bounded retries** | **办法：四个检测器 + 有限次重试** |
| Signature window — tool name + argument hash, k=5 | 工具签名窗口：工具名 + 规范化参数哈希，窗口 k=5 |
| repeat ≥ 3 inside the window triggers the guard | 窗口内重复 ≥3 次即触发守卫 |
| State-hash repetition — identical state reached again | 状态哈希重复：又回到了完全相同的状态 |
| Facts delta = 0 — verified-fact set unchanged | 事实增量为 0：已核实事实集合没有增加 |
| Bounded back-edges — limited replans per node | 有界回退边：每个节点允许的重规划次数有限 |
| **Verify** — deterministic injection of a repeated tool sequence and of zero-progress states | **验证：** 确定性注入"重复工具序列"与"零进展状态" |
| *(footnote)* measured: 3/3 detected · normal-run false positives 0 · termination within six steps | *（脚注）* 实测：3/3 检出 · 正常 run 误报 0 · 6 步内终止 |
| **Takeaway:** First replan, then hard stop | **收口：** 先重规划，再硬停 |

**Why these solutions are needed**

1. **空转是"静默烧钱"**：多 agent 长跑最常见的是"同一查询反复调用""摘要复述无新增"，token 线性上涨而产出为零，无人值守时没人会发现——必须让机器自己判定。
2. **无限重试 = 无限循环**：条件边若无次数上限，失败会被反复重试。把回退次数写进状态并以"每节点上限"约束，才能保证成本有界。
3. **"停滞"要有直接信号**：只看"有没有报错"没用；**已核实事实增量 = 0** 才是停滞的直接判据，配合工具签名成环与状态哈希重复，覆盖三类不同的原地打转。
4. **处置必须分级且留痕**：第一次 replan（还可能救回来），第二次 abort 并 annotate（不再烧预算）；这与全局升级阶梯一致，也让"处置正确率"可统计。

---

## Slide 10 · Problem 3 — Budget

| English (as on the slide) | 中文对应 |
|---|---|
| PROBLEM 3 · BUDGET | 问题 3 · 预算 |
| **How it stops burning money** | **如何让它不再烧钱** |
| 预算失控：四维看门狗 *(标题下灰字注解)* | （即为本页中文注解） |
| **Hero:** The watchdog warns at 80% and stops at 100% | **核心结论：** 看门狗：80% 告警、100% 停止 |
| 3/3 overruns stopped, annotated | 3/3 次超预算都被停止并标注 |
| per-node timeout, recursion limit | 另有节点级超时与图级递归上限 |
| **Problem** | **问题** |
| an unattended run has no natural cost ceiling | 无人值守的 run 没有天然的"成本天花板" |
| "let it finish" is the wrong default | "让它跑完"是默认设置里的错误答案 |
| **Methods — a watchdog with teeth** | **办法：长牙齿的看门狗** |
| Four dimensions — tokens, seconds, cost, steps | 四个维度：token、秒数、成本、步数 |
| Budget from config — overridable per topic | 预算来自配置，可按 topic 覆盖 |
| Early degradation — cheaper tier, shorter retrieval | 提前降级：换便宜档、缩短检索批次 |
| 80% warn is non-blocking; 100% stops — annotates | 80% 只告警不阻断；100% 直接停止并在报告里标注 |
| Every decision emits events — metric plus guard_trigger | 每次处置都写事件：metric + guard_trigger |
| **Verify** — inflate token counts until the ceiling and watch the ladder move | **验证：** 把 token 计数灌到上限，观察阶梯是否按 80/100 动作 |
| *(footnote)* related ceilings: per-node timeout · graph recursion limit · 4 KB per step | *（脚注）* 相关上限：节点超时、图递归上限；检查点 4 KB/超级步 |
| **Takeaway:** Warn at 80%, stop at 100% | **收口：** 80% 告警，100% 停止 |

**Why these solutions are needed**

1. **无人值守时成本没有上限就会失控**：如果只有"跑到自然结束"，一次异常循环或一次 provider 卡顿就可能把预算跑穿——必须把预算做成一等公民。
2. **四个维度抓的是不同的失控形态**：token 抓"话多"、秒数抓"卡住"、成本抓"贵档滥用"、步数抓"原地打转"，缺一维就会漏掉一种。
3. **提前降级比硬停更划算**：接近上限时先换便宜档、缩短检索，往往能把活干完；真到 100% 才终止——这是"能用"与"可控"之间的折中。
4. **不写事件 = 指标看不见**：我们实际踩过"超时只写日志没写事件"的坑，导致该族检出率恒为 0。所以规定**凡会被指标/回放消费的事实必须写事件**，80% 告警也是可审计的事实。

---

## Slide 11 · Problem 4 — Hallucination and factuality

| English (as on the slide) | 中文对应 |
|---|---|
| PROBLEM 4 · HALLUCINATION | 问题 4 · 幻觉与事实性 |
| **No unsupported claim ships** | **没有证据支撑的断言行不通** |
| 如何控制幻觉与事实性 *(标题下灰字注解)* | （即为本页中文注解） |
| **Hero:** No claim ships without a resolvable citation | **核心结论：** 引用无法回查的断言一律不许出厂 |
| citations resolved 1.0 | 引用可回查率 1.0 |
| grounding 0.7949 (self-labelled) | grounding 0.7949（模型自报标签） |
| **Problem** | **问题** |
| long chains invite fabricated numbers and silent contradictions | 长链条容易编造数字、也会悄悄产生互相矛盾的结论 |
| factuality is enforced by contract, not by tone | 事实性靠"契约强制"，不是靠语气叮嘱 |
| **Methods — factuality by contract** | **办法：用契约保证事实性** |
| Claim + evidence are one unit — no citation, no claim | 断言与证据是一个整体：没有引用就不算断言 |
| Citations must resolve — paper_id + snippet | 引用必须能在语料快照中定位：paper_id + 片段 |
| Contradictions are first-class — never averaged | 矛盾是一等状态：显式呈现，绝不取平均糊过去 |
| Refusal is legal — name the missing evidence | 拒答是合法输出：必须说明缺什么证据 |
| Numbers carry provenance — tool results only | 数值必须带出处：只来自工具结果 |
| **Verify** — scripted citation resolvability over the frozen corpus snapshot | **验证：** 在冻结语料快照上脚本化检查引用可回查 |
| *(footnote)* grounding 0.7949 is model-self-reported · gold facts + cross-vendor judge: P3 | *（脚注）* 0.7949 目前是模型自报标签；gold 事实集 + 异源 judge 属 P3 |
| **Takeaway:** Unsupported claims cannot pass | **收口：** 无支撑的断言过不了关 |

**Why these solutions are needed**

1. **长程任务最容易在"数值/结论"上失真**：链条越长，模型越倾向于补一个"看起来合理"的数字；且两次回答可能互相矛盾而不自知。
2. **"语气式"约束不可靠**：说"请务必准确"没有判定能力。把事实性做成 **schema 级契约**（claim 与 citation 绑定），才能被脚本强制、被计数。
3. **幻觉必须可量化**：只有"引用能在快照里定位"这条客观判据，才能算出**可回查率**与幻觉率；定位失败就标 unverified 并计入幻觉率。
4. **矛盾不能取平均**：平均会把两个来源的冲突"发明"成一个新事实，属于最危险的静默错误；应显式呈现分歧并给出权威性/时效性权衡。
5. **拒答合法**：把"证据不足"设为合法输出并要求说明缺口，才能避免"编一个凑数"，也让拒答恰当性成为可评测指标。

---

## Slide 12 · Problem 5 — Context growth

| English (as on the slide) | 中文对应 |
|---|---|
| PROBLEM 5 · CONTEXT GROWTH | 问题 5 · 上下文膨胀 |
| **Keep a long run inside the window** | **让长跑始终装得进窗口** |
| 长跑上下文膨胀：折叠与分层 *(标题下灰字注解)* | （即为本页中文注解） |
| **Hero:** State holds summaries and pointers, never raw text | **核心结论：** 状态里只放摘要与指针，绝不放原文 |
| folding is an explicit node | 折叠是一个显式节点 |
| three memories · fixed slots | 三层记忆 + 固定注入槽 |
| **Problem** | **问题** |
| state, tool results and retrieval history grow without bound | 状态、工具结果与检索历史会无界增长 |
| local tiers are tighter still | 本地模型档的窗口更紧 |
| **Methods — fold explicitly, store pointers** | **办法：显式折叠，只存指针** |
| Summaries and pointers only — paper_id, event id | 只存结构化摘要与指针：paper_id、事件 id |
| Budget before every call — folding is a node, never implicit | 每次调用前先算预算：折叠是节点，不是隐式行为 |
| Folding rules — history → points; dialogue → window | 折叠规则：检索历史→要点+引用；旧对话→滑动窗口+摘要 |
| Three-layer memory — topic / evidence / report history | 三层记忆：topic 长期状态 / 证据库 / 周报历史 |
| Fixed injection slots — system / user / tool cards | 固定注入槽：system / user / 工具结果卡 |
| **Verify** — long-run stress test, state-size events, folding-granularity experiment | **验证：** 长跑压测、状态体积事件、折叠粒度实验 |
| *(footnote)* status: designed and instrumented, not yet measured — Phase 0 volume small | *（脚注）* 状态：已设计并埋点，尚未实测（Phase 0 数据量太小） |
| **Takeaway:** Fold first, then route | **收口：** 先折叠，再路由 |

**Why these solutions are needed**

1. **小时级 run 的状态会无界膨胀**：工具结果、检索历史、中间产物如果都留在上下文里，窗口与显存会先耗尽，run 在中途崩掉。
2. **本地档更紧**：本地 7–14B 的窗口远小于云端，同一套策略必须在"更小预算"下也能跑通，所以不能依赖"云端够大"。
3. **折叠必须显式化**：把折叠做成**图上节点**，才能单测、才能在事件里看到"何时折叠、折叠了什么"；隐式摘要（藏在链内部）无法解释也无法复现。
4. **指针化让状态可重读**：状态只留 `paper_id`/事件 id，原文留在文件系统与存储里——状态小、可重读，也让"恢复"不依赖塞满上下文。
5. **三层记忆 + 固定槽防止"全量倒进去"**：不同记忆各有读取接口，注入槽形状固定，保证 prompt 结构稳定、可复现。

---

## Slide 13 · Problem 6 — Validating tool and MCP returns

| English (as on the slide) | 中文对应 |
|---|---|
| PROBLEM 6 · TOOL AND MCP RETURNS | 问题 6 · 工具与 MCP 返回值 |
| **How we validate what tools return** | **如何校验工具的返回值** |
| 如何验证工具/MCP 返回的数据是否合法 *(标题下灰字注解)* | （即为本页中文注解） |
| **Hero:** Four of six layers need no LLM to decide | **核心结论：** 六层校验中前四层不需要 LLM |
| 90%+ decided without an LLM | 90%+ 的合理性判定是确定性的 |
| critical actions fail closed | 关键动作 fail-closed（校验不过就不落地） |
| **Problem** | **问题** |
| tool output is untrusted data, and "reasonable" hides four questions | 工具返回是**不可信数据**，而"是否合理"其实混着四个不同问题 |
| protocol validity · numeric domains · cross-field · semantics | 协议合法性 · 数值域 · 跨字段一致 · 语义成立 |
| **Methods — six layers, four need no LLM** | **办法：六层判定，前四层不用 LLM** |
| L0 protocol — JSON-RPC validity, isError, schema, enums | L0 协议层：JSON-RPC 合法性、isError、output schema、类型与枚举 |
| L1 domain rules — 0 ≤ ratio ≤ 1, cited_by ≥ 0, year ≤ current | L1 确定性领域层：比例 0–1、cited_by ≥ 0、年份 ≤ 今年等 |
| L2 cross-source recompute — a second source | L2 交叉验证层：用独立的第二源重算关键数值 |
| L3 statistical anomaly — z-score / IQR, count spikes | L3 统计异常层：与历史分布比较（z-score/IQR）、计数突变 |
| L4 LLM for semantics only — rubric, cross-vendor, sampled | L4 语义判读层：仅处理语义（rubric、异源、抽样） |
| L5 human spot-check — calibrates the judge, not the data | L5 人工层：校准 judge，而不是逐条校对数据 |
| **Verify** — fake tool results: bad numbers, missing fields, poisoned text | **验证：** 构造假返回（坏数值、缺字段、注入指令文本）测拦截率与误报 |
| *(footnote)* fail-closed consequences: no graph write, no evidence-pool entry, no report claim | *（脚注）* fail-closed 的后果：不写图库、不进证据池、不写进报告 |
| **Takeaway:** No LLM until layer four | **收口：** 到第四层之前不用 LLM |

**Why these solutions are needed**

1. **工具/MCP 返回是不可信数据**：可能字段缺失、数值越界、跨字段矛盾，甚至夹带指令性文本（注入）。它和"模型输出"一样需要校验，不能默认可信。
2. **"合理"是四个不同问题**：协议合法性、数值域、跨字段一致、语义成立——混在一起就只能"什么都问 LLM"，又贵又不稳；拆层之后**前四层用确定性代码即可判定**。
3. **90%+ 的数值合理性可以静态判定**：比值范围、非负计数、年份上限、引用可回查、单位、白名单、时效、去重——这些都是规则可判的，交给 LLM 是浪费。
4. **关键动作必须 fail-closed**：一个坏数值若被静默写进图库或报告，就会污染语料与评测（且不报错）。因此规定校验不过 → 不写库、不进证据池、不进报告。
5. **LLM 只做开放语义，且要异源+抽样**：语义判读用 rubric 化 judge、跨厂商、抽样并缓存；人工只用于校准 judge，不做全量校对。

---

## 附：六个问题与办法的一句话索引

| # | 失败模式（不做会怎样） | 对应办法 | 可核验证据 |
|---|---|---|---|
| 8 | 长跑跑偏并被下游放大 | Scope Anchor + 阶段契约 + 代码层硬约束 + 守卫 | 15/15 检出、0 误报、阈值 0.0777/0.0867 |
| 9 | 原地打转、静默烧钱 | 三级检测（签名/状态哈希/事实增量）+ 有界回退 | 3/3 检出、6 步内终止 |
| 10 | 成本无上限、跑到失控 | 四维看门狗 + 80/100 阶梯 + 事件留痕 | 3/3 超预算被停止并标注 |
| 11 | 编造数字、矛盾被平均掉 | claim+evidence 契约 + 引用可回查 + 矛盾一等 + 拒答合法 | 引用可回查率 1.0；grounding 0.7949（自报） |
| 12 | 状态膨胀撑爆窗口 | 摘要+指针、折叠节点、三层记忆、固定注入槽 | 已设计埋点，Phase 1 压测 |
| 13 | 坏数据静默入库/入报告 | 六层判定（前四层无 LLM）+ fail-closed | 假返回注入测试；关键动作不落地 |
