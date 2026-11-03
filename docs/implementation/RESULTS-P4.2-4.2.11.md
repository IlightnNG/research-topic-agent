# RESULTS · Phase 4.2.11 Report Optimization

> Status：in progress
> Date：2026-11-03
> Done：4.2.11.1 section quality metrics
> Open：LLM audit hard gate / fulltext / API resume / UX

---

## 1. Done · Section quality metrics

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

The metrics are recomputed from the report and evidence, not trusted from the writer.

---

## 2. Real 100-paper metrics

```text
papers             100
fulltext           35
claims             186
sections           23
word_count         5479
citation_coverage  1.0
empty sections     0
reference problems 0
cited claims       186
uncovered claims   0
duplicate sentences 6
accepted           true
```

Interpretation:

```text
硬门禁通过
duplicate_sentences 是质量信号，暂不作为 hard fail
```

---

## 3. LLM audit status

Attempted to use LLM audit on the full report.

Observed:

```text
audit JSON parse failures on long report input
unstable scoring
```

Decision:

```text
LLM audit remains advisory
deterministic quality gate remains hard
```

Do not make LLM audit the only hard gate until prompt/JSON reliability is fixed.

---

## 4. Open items

### 4.2.11.2 LLM audit hard gate

```text
trace-aware report audit prompt
JSON retry/repair
score calibration
hard/advisory policy
```

### 4.2.11.3 Fulltext

```text
100 papers / 35 fulltext
needs multi-source PDF/HTML
```

### 4.2.11.4 API resume

```text
CLI resume verified
API real pause/restart/resume still needs test
```

### 4.2.11.5 Report UX

```text
5 Node progress
section progress
quality gate display
failed section retry
```

---

## 5. Tests

```text
126 passed
ruff clean
```

New coverage:

```text
section quality metrics
metrics present in report quality
strict quality failure on small report
```

---

## 6. Next

```text
1. Fix LLM audit JSON/reliability
2. Improve fulltext ratio
3. Real API interrupt/resume test
4. Report progress UI
```
