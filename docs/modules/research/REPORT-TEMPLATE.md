# Report Template

> Used by `report.write_section` as a format reference.
> The renderer adds the report and section titles; the LLM must return the body only.

---

## Template

```markdown
# <Report title>

## At a Glance

Two to four sentences summarizing the corpus, its main themes, and its scope.

## Papers 1-5

**<paper_id>.** One paragraph for the paper, using supplied claims only.
Every factual sentence ends with its [C#] citation.

## Papers 6-10

**<paper_id>.** Same structure as above.

## Cross-Paper Synthesis

Two to three paragraphs covering agreements, tensions, and open gaps across papers.

## Paper Index

- <paper_id>: <paper title>
```

---

## Rules

```text
do not invent papers, claims, numbers, or citations
every factual sentence cites [C#]
do not output a section heading
do not repeat the report title
paper_analysis: one paragraph per paper id in the section
overview: 2–4 sentences
synthesis: 2–3 paragraphs
paper_index: bullet list only
```

---

## Inline formatting

Markdown is rendered by `marked` and sanitized by `DOMPurify`.

Supported:

```text
headings
paragraphs
lists
tables
code blocks
blockquotes
links
bold / italic
```

Citation tokens such as `[C12]` become clickable paper links when they match
the report's `paper_links`.
