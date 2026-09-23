# Grooming E6.07 — Lint improvements: structural analysis

- **Status:** Prêt
- **Date:** 2026-09-23 (replaces 2026-09-04)

## Context

lint.py and `lore-mcp lint` already implemented
(text_density, noise_sections, verdict). This
grooming adds structural analysis metrics.

## Problem

lint.py only computes text_density and noise
sections. Missing structural analysis that
directly impacts RAG retrieval quality:
- 80% RAG failures trace to preprocessing (TDS)
- Heading-aware chunking: +78.6% retrieval (D-RAC)
- Hierarchical chunking: 61%→89% accuracy (NVIDIA)
- Document without headings = blind chunking
- Base64 in embeddings = pure noise

## Solution

A `lore-mcp lint` subcommand that analyzes
markdown sources and produces a quality report.
Runs before indexing — does not modify files.

### Metrics per file

| Metric | What it measures |
|--------|-----------------|
| **text_density** | Ratio alpha chars / total chars. Low = noise (numbers, symbols) |
| **heading_count** | Number of ## and ### headings. Zero = unstructured |
| **avg_section_length** | Average words per section. Low = fragmented |
| **empty_sections** | Sections with < 5 words |
| **noise_sections** | Sections where alpha ratio < 0.3 (numeric tables, coordinates) |
| **image_count** | Number of markdown images (before stripping) |
| **word_count** | Total words |

### Output

Markdown table sorted by text_density (worst
first), with a per-file verdict:

| Verdict | Criteria |
|---------|----------|
| **good** | text_density ≥ 0.7, no noise sections |
| **warn** | text_density ≥ 0.5 or has noise sections |
| **poor** | text_density < 0.5 or majority noise sections |

### CLI invocation

```
lore-mcp lint manifest.yaml --docs-dir /path/
lore-mcp lint manifest.yaml --docs-dir /path/ --config models.yaml
lore-mcp lint manifest.yaml --docs-dir /path/ --verbose
lore-mcp lint manifest.yaml --docs-dir /path/ --report report.md
```

- `manifest.yaml` (positional): source file list
  (same pattern as `lore-mcp build`)
- `--docs-dir`: base directory to resolve manifest
  paths
- `--config`: when provided, loads the embedding
  model and adds heading/content similarity
  scoring. Without it, only text heuristics are
  applied (with a warning)
- `--verbose`: per-section detail
- `--report <path>`: markdown report output
- `--quiet`: silence output (CI mode, exit code
  only)
- Exit code 0 = all good/warn, 1 = any poor

### Two analysis levels

**Text heuristics (always, no model):**
- text_density, heading_count, avg_section_length
- empty_sections, noise_sections, word_count

**Embedding similarity (with --config):**
- heading/content cosine similarity per section
- Low similarity = content doesn't match heading
  (noise, wrong section, OCR artifacts)
- Uses the first embedding model from config

### Implementation

1. `lint.py` module with `analyze_file(path)` →
   file metrics dict
2. `analyze_file_with_embedder(path, embedder)` →
   adds similarity scores
3. `lint_sources(docs_dir, manifest_path,
   embedder=None)` → list of file reports
4. CLI subcommand in `server.py`

### Scope

- Read-only analysis, no file modification
- Markdown only (E6.06 handles other formats)
- No automatic exclusion from indexing (user
  decides)

## New metrics

| Metric | Type | Description |
|--------|------|-------------|
| heading_depth | int | Max depth (H1=1, H4=4) |
| heading_ratio | float | Headings per 1000 words |
| heading_issues | list | Level skips (## → ####) |
| structure_score | float | 0.0-1.0 composite |
| base64_count | int | Residual base64 patterns |
| completeness_ratio | float | output/input size |

### structure_score formula

```python
score = 0.0
if heading_count > 0:
    score += 0.3
if heading_depth >= 2:
    score += 0.2
if heading_depth >= 3:
    score += 0.1
if heading_ratio >= 2.0:
    score += 0.2
if not heading_issues:
    score += 0.2
```

### Verdict integration

Current: density < 0.5 → poor
Added: structure_score < 0.1 → poor
       structure_score < 0.3 → warn

### Excluded from scope

- Numeric density: false positives (financial
  tables are valid RAG content)
- Header/footer detection: needs LLM
- Embedding similarity: deferred (MVP2 in
  original grooming)

## DoD

1. heading_depth, heading_ratio in report
2. heading_issues (level skips)
3. structure_score (0.0-1.0)
4. base64_count
5. completeness_ratio
6. Verdict integrates structure_score
7. Tests

## Sources

- D-RAC heading-aware chunking: arXiv 2609.24220
- LlamaParse quality scoring: theneuralbase.com
- 10 RAG mistakes: towardsdatascience.com
- NVIDIA hierarchical chunking: 61%→89%

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
