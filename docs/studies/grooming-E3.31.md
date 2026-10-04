# Grooming E3.31 — Structured data to knowledge

## Context

Raw tabular data (JSON, CSV, XLSX) has low
semantic value for vector search. Current
pipeline:
- JSON → markitdown → raw JSON text (no
  conversion, zero headings, poor verdict)
- CSV → markitdown → markdown table (some
  structure, but no narrative)
- XLSX → Docling → markdown tables (heading-free,
  low text density, poor verdict)

These formats need transformation into
searchable text. E12.109 will index them despite
poor quality, but retrieval will be mediocre
without semantic enrichment.

## Approaches evaluated

### 1. Template narration (no LLM)

Detect data structure (array of records, nested
objects, flat key-value) and generate natural
language descriptions:

```
On 2022-11-20, Qatar played against Ecuador
in Matchday 1 (Group A) at Al Bayt Stadium.
Final score: 0-2.
  Goal: Enner Valencia at minute 16 (penalty)
  Goal: Enner Valencia at minute 31
```

Pros: fast, deterministic, no LLM cost.
Cons: requires schema detection heuristics,
generic templates may produce awkward text.

### 2. LLM narration

Send rows/sections to LLM with prompt:
"Convert this data into a readable narrative
paragraph that preserves all values."

Pros: highest quality, handles any structure.
Cons: 1 LLM call per batch of rows, cost
proportional to data size.

### 3. Hybrid (schema + column descriptions)

Auto-detect schema, generate column descriptions,
then narrate groups of rows:

Step 1: Extract schema (column names, types,
sample values) — no LLM needed.
Step 2: Generate column descriptions — LLM or
heuristic from column names.
Step 3: Narrate rows in groups — template or LLM.

### 4. Statistical summaries

For numeric data: min, max, avg, counts, top-N
values. Adds high-level understanding without
per-row narration.

## Recommendation

**Hybrid approach in 3 MVPs:**

### MVP1 — Schema extraction + markdown headings

No LLM. Detect structure and add headings:
- JSON array: `## {collection_name}` heading +
  one section per record group
- CSV: `## {filename}` heading + column
  descriptions from header row
- XLSX: `## {sheet_name}` per sheet

Output has headings → passes quality gate.
Heading context improves chunking via
HybridChunker.

Implementation: new `narrate_structured(text,
format)` function in `preprocess/clean.py` or
a new `preprocess/narrate.py` module. Called
after `parse_to_markdown` when format is
`markitdown` or content is detected as
tabular.

### MVP2 — Template narration

No LLM. Row-to-sentence templates for common
patterns:
- Array of records: key-value pairs as sentences
- Flat objects: "The {key} is {value}."
- Nested: recursive flattening with indentation

Heuristics: detect date columns, numeric
columns, categorical columns. Adapt template
per column type.

### MVP3 — LLM narration (optional)

Integrate as enrich technique `narrate`.
`--enrich narrate` generates LLM-quality
descriptions. Uses existing LLM infrastructure
(enrich.py, llm.py).

## DoD per MVP

### MVP1
- JSON/CSV/XLSX preprocessed output has at least
  one heading
- Quality gate passes (structure_score > 0)
- No LLM dependency
- Test: worldcup.json → heading + sections
- Test: aout-2026.xlsx → sheet headings

### MVP2
- Records converted to sentences
- Searchable for entity queries ("Qatar vs
  Ecuador", "August 2026 calendar")
- Test: search for "Qatar Ecuador" returns
  worldcup source

### MVP3
- LLM narration produces natural language
- Quality comparable to manually written docs
- Configurable via enrich.techniques

## Dependencies

- E12.109 (index poor sources) — MVP1 improves
  quality so sources are no longer poor
- Existing parse pipeline (markitdown, Docling)
  — narration is a post-parse step

## Effort

MVP1: small (schema detection + heading
injection). MVP2: medium (template engine).
MVP3: small (reuse existing LLM enrichment).
