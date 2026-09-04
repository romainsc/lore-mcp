# Grooming E6.07 — Source quality analysis

- **Status:** En attente validation
- **Date:** 2026-09-04

## Problem

lore-mcp indexes any markdown file without
assessing its quality. Bad sources produce bad
chunks which degrade retrieval quality. Current
corpus contains:

- Numeric sequences (ANN weight tables rendered
  as lists of numbers)
- Near-empty sections (just a heading and one
  word)
- Slide captions with no textual content ("P",
  "f", "Slide 3 — Disclaimers")
- Duplicate or near-duplicate sections
- Broken markdown (unclosed fences, skipped
  heading levels)

There is no way to know before indexing which
files will produce useful chunks.

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

### Integration

- `lore-mcp lint --docs-dir <path>` — all .md
- `lore-mcp lint --manifest <path> --docs-dir <path>` — manifest files only
- Exit code 0 = all good/warn, 1 = any poor
- `--verbose` shows per-section detail
- `--report <path>` writes markdown report

### Implementation

1. `lint.py` module with `analyze_file(path)` →
   file metrics dict
2. `lint_sources(docs_dir, manifest_path)` →
   list of file reports
3. CLI subcommand in `server.py`
4. No external dependency

### Scope

- Read-only analysis, no file modification
- Markdown only (E6.06 handles other formats)
- No automatic exclusion from indexing (user
  decides)

## DoD

1. `lore-mcp lint` produces quality report
2. Per-file metrics: text_density, heading_count,
   avg_section_length, empty_sections,
   noise_sections, word_count
3. Verdict per file (good/warn/poor)
4. Manifest support
5. `--verbose` per-section detail
6. `--report` markdown output
7. Exit code 1 on poor files
8. Tests TDD
9. Documentation updated

## MVP

1. `analyze_file` + `lint_sources` with metrics
2. CLI subcommand with table output
3. Manifest support

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
