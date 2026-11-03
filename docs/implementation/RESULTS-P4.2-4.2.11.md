# RESULTS · Phase 4.2.11 Report Optimization

> Status：done；hard audit accepted on final 100-paper run
> Date：2026-11-03
> Report：100 papers / 98 fulltext / 196 claims / 23 sections

---

## 1. Section quality metrics · done

Added:

```text
report.quality.metrics
report.quality.check
section_metrics
```

Per section:

```text
section_id
kind
words
citations
claim_refs
problems
```

Report-level:

```text
papers
fulltext
claims
sections
word_count
citation_coverage
empty_sections
reference_problem_sections
cited_claims
uncovered_claims
duplicate_sentences
```

---

## 2. Real 100-paper metrics · 98 fulltext

```text
papers             100
fulltext           98
claims             196
sections           23
word_count         5115
citation_coverage  1.0
empty sections     0
reference problems 0
cited claims       190
uncovered claims   6
duplicate sentences 0
accepted           true
```

---

## 3. LLM audit reliability · hard gate

Added:

```text
LLMAuditor.audit_summary()
```

Instead of sending the full 5k-word report, audit uses a compact metrics summary:

```text
papers / fulltext / claims / sections /
words / citation_coverage / empty / uncovered / duplicate
```

This avoids long-document JSON instability.

Status:

```text
compact audit JSON works
explicit reject -> hard fail
audit unavailable -> fail-open + status=unavailable
final 100-paper report: audit accepted
```

---

## 4. Fulltext enrichment · 35 → 98

Added:

```text
scripts/enrich_fulltext.py
```

Behavior:

```text
try PDF URL
fallback HTML URL
write fulltext/{paper_id}.txt
report success/failure
```

Result:

```text
start        35 / 100
after       98 / 100
failed       2
```

Corpus:

```text
D:\lit-agent-store\v2-eval\gold\corpora\agents-fulltext
```

---

## 5. API real pause / resume · passed

Probe:

```text
create API run
wait until report.write is running
POST /pause
wait for paused
POST /resume
wait for succeeded
```

Result:

```text
run_id      run-b589470f5d93
state       succeeded
papers      100
fulltext    98
claims      196
sections    23
word_count  5204
```

No duplicate report; resumed report completed.

---

## 6. Report progress UI · section bar

Added:

```text
web/src/components/report/SectionProgress.vue
```

`report.write` emits:

```text
section.written
  section_id
  written
  remaining
  total
```

UI shows a section-level progress bar inside the `report.write` Node.

Frontend build:

```text
npm run build passed
```

---

## 7. Tests

```text
128 passed
ruff clean
npm run build passed
```

New coverage:

```text
compact audit JSON
section quality metrics
strict quality failure
section cursor loop
```

---

> 4.2.11 complete。剩余改进属于 4.3 / backlog：2/100 fulltext、audit 校准、parallel sections。
